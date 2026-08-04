import logging
from collections.abc import AsyncGenerator, Iterable
from time import monotonic
from uuid import uuid4

from fastapi import Request, Response
from loguru import logger

from middleware import MiddlewareBase
from settings import settings


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = logging.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def init_logging():
    # Skip inited in current process loguru
    if getattr(logger, "inited", False):
        return

    # Add process enumerated index column when workers used
    kwargs = {}
    process_name = "main"
    if (workers := settings.server.workers) and workers > 1:
        from multiprocessing import current_process

        if len(x := current_process().name.rsplit("-", maxsplit=1)) == 2:
            process_name = x[1]
        kwargs["format"] = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level:<8}</level> | "
            f"<yellow>{process_name:<4}</yellow> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )

    # Initialize loguru console logger
    logger.remove()
    if (log_console_kw := settings.log.console_kw)["level"] is not None:
        import sys

        logger.add(sys.stderr, **kwargs, **log_console_kw)

    # Initialize loguru file logger
    if (log_file_kw := settings.log.file_kw)["level"] is not None:
        logger.add("logs/auth.log", **kwargs, **log_file_kw)

    # Skip uvicorn access log if disabled
    logger_names = ["uvicorn.error", "uvicorn.asgi"]
    if settings.server.access_log is True:
        logger_names += "uvicorn.access"

    # Intercept active uvicorn loggers by loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in logger_names:
        intercepted = logging.getLogger(name)
        intercepted.handlers = [InterceptHandler(level=0)]
        intercepted.propagate = False

    # Set loguru inited in current process
    logger.inited = True
    logger.trace(f"Logger inited in {process_name} process")


class LoggerMiddleware(MiddlewareBase):
    @staticmethod
    def get_log_level(status_code: int) -> str:
        return ("NOTSET", "INFO", "SUCCESS", "INFO", "WARNING", "ERROR")[status_code // 100]

    async def handle(self, request: Request) -> AsyncGenerator[Iterable | Response, Response]:
        """Gather additional request and response information to logs"""
        start_time = monotonic()

        _header = request.headers.get
        client = {
            "client_ip": _header("X-Forwarded-For", request.client.host),
            "user_agent": _header("user-agent", ""),
        }
        details = {"method": request.method, "path": request.url.path}

        with logger.contextualize(request_id=_header("X-Request-ID", str(uuid4()))):
            logger.info("[ In] {method} {path}", **client, **details)

            response = yield
            duration_ms = (monotonic() - start_time) * 1000

            code = response.status_code
            msg = "[{status:3}] {method} {path} ({duration:.3f} ms)"
            logger.log(self.get_log_level(code), msg, status=code, duration=duration_ms, **details)

        yield
