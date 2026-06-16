from threading import Thread

import pytest
from httpx import Client, get
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uvicorn import Config, Server

from database import get_test_data
from main import app
from models import TableBase
from settings import settings

db_engine = create_engine(settings.postgres.test_url)
_base_url = f"http://{settings.host}:{settings.port}"


@pytest.fixture(scope="session")
def server():
    """TestClient is not working due to event loop closed conflicts between httpx and asyncpg"""
    server = Server(Config(app, port=80))

    server_thread = Thread(target=server.run, daemon=True)
    server_thread.start()

    yield get(_base_url)

    server.should_exit = True
    server_thread.join(timeout=5)


@pytest.fixture(scope="class")
def db_recreate(server):
    TableBase.metadata.drop_all(db_engine)
    TableBase.metadata.create_all(db_engine)
    with sessionmaker(db_engine).begin() as session:
        session.add_all(get_test_data())

    return server


@pytest.fixture(scope="class")
def client(db_recreate):  # noqa: ARG001 fixture-related argument
    return Client(base_url=_base_url)
