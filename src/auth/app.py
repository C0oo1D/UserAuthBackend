from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from starlette.types import Lifespan

from cache import Cache
from database import DBMiddleware
from logger import LoggerMiddleware
from routers import secure, user
from sessions import SessionMiddleware, session_lifespan


def lifespans(*callables: Lifespan):
    @asynccontextmanager
    async def wrapper(app_instance: FastAPI):
        async with AsyncExitStack() as stack:
            add = stack.enter_async_context
            [await add(lifespan(app_instance)) for lifespan in callables]
            yield

    return wrapper


logger.trace("App is loading")

app = FastAPI(lifespan=lifespans(Cache, session_lifespan))
app.add_middleware(SessionMiddleware)
app.add_middleware(DBMiddleware)
app.add_middleware(LoggerMiddleware)
app.include_router(user.router)
app.include_router(secure.router)

logger.trace("App is loaded")
