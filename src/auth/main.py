import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from starlette.types import Lifespan

from cache import Cache
from database import DBMiddleware, create_db_lifespan
from routers import secure, user
from sessions import SessionMiddleware, session_lifespan
from settings import settings

logger = logging.getLogger()
logger.setLevel(logging.DEBUG if settings.debug else logging.ERROR)
logger.info("App is loading")


def lifespans(*callables: Lifespan):
    @asynccontextmanager
    async def wrapper(app_instance: FastAPI):
        async with AsyncExitStack() as stack:
            add = stack.enter_async_context
            [await add(lifespan(app_instance)) for lifespan in callables]
            yield

    return wrapper


app = FastAPI(lifespan=lifespans(create_db_lifespan, Cache, session_lifespan))
app.add_middleware(SessionMiddleware)
app.add_middleware(DBMiddleware)
app.include_router(user.router)
app.include_router(secure.router)
logger.info("App is loaded")


def run():
    from uvicorn import run

    logger.info("App is starting")
    run(app, host=settings.host, port=settings.port)
    logger.info("App is closed")


if __name__ == "__main__":
    run()
