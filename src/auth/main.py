import logging

from fastapi import FastAPI

from database import DBMiddleware, create_db_lifespan
from routers import secure, user
from sessions import SessionMiddleware
from settings import settings

logger = logging.getLogger()
logger.setLevel(logging.DEBUG if settings.debug else logging.ERROR)
logger.info("App is loading")


app = FastAPI(lifespan=create_db_lifespan)
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
