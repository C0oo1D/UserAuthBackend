import logging

from fastapi import FastAPI

from database import DBMiddleware, create_db_lifespan
from routers import user, secure
from sessions import SessionMiddleware
from settings import debug


logging.getLogger().setLevel(logging.DEBUG if debug else logging.ERROR)
logging.info('App is loading')


app = FastAPI(lifespan=create_db_lifespan)
app.add_middleware(SessionMiddleware)
app.add_middleware(DBMiddleware)
app.include_router(user.router)
app.include_router(secure.router)
logging.info('App is loaded')


def run():
    from uvicorn import run

    logging.info('App is starting')
    run(app, port=80)
    logging.info('App is closed')


if __name__ == '__main__':
    run()
