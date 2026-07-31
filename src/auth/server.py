import asyncio
import logging
import socket
import sys
from asyncio import CancelledError
from pathlib import Path

from loguru import logger
from uvicorn import Config, Server
from uvicorn.main import STARTUP_FAILURE
from uvicorn.supervisors import ChangeReload, Multiprocess

from database import create_db
from logger import init_logging
from settings import settings


def _uvicorn_run(config: Config, server: Server):
    """Cut Config and Server initialization from uvicorn.run (for loggers intercept)"""
    if (config.reload or config.workers > 1) and not isinstance(config.app, str):
        logging.getLogger("uvicorn.error").warning(
            "You must pass the application as an import string to enable 'reload' or 'workers'."
        )
        sys.exit(1)

    try:
        if config.should_reload:
            sock = config.bind_socket()
            ChangeReload(config, target=server.run, sockets=[sock]).run()
        elif config.workers > 1:
            sock = config.bind_socket()
            Multiprocess(config, target=server.run, sockets=[sock]).run()
        else:
            server.run()
    except KeyboardInterrupt:
        pass  # pragma: full coverage
    finally:
        if config.uds and Path.exists(config.uds):
            Path.unlink(config.uds)

    if not server.started and not config.should_reload and config.workers == 1:
        sys.exit(STARTUP_FAILURE)


class LoggedServer(Server):
    """Add loguru at each server process"""

    def run(self, sockets: list[socket.socket] | None = None) -> None:
        init_logging()
        try:
            super().run(sockets)
        except OSError as exc:
            logger.error(f"Restarting process due to OSError: {exc}")
        finally:
            logger.complete()


def run(config: Config | None = None, server: Server | None = None):
    init_logging()
    logger.info("App is starting")

    asyncio.run(create_db())

    if config is None:
        config = settings.server.config
    if server is None:
        server = LoggedServer(config=config)
    try:
        _uvicorn_run(config, server)
    except CancelledError:
        logger.exception("App is failed to finish correctly")
    else:
        logger.info("App is finished")
    finally:
        logger.complete()
