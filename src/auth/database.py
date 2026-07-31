from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, suppress
from typing import Annotated

from asyncpg import ConnectionDoesNotExistError, InvalidAuthorizationSpecificationError
from fastapi import Depends, Request
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from example_data import get_example_data
from middleware import MiddlewareBase
from models import TableBase
from settings import settings

engine = create_async_engine(settings.postgres.app_url, echo=settings.db_echo)
db_maker = async_sessionmaker(engine, autoflush=False)


async def _create_db_and_user():
    logger.info("Creating database and owner (only if they do not exist)")
    pg = settings.postgres
    user = pg.user
    password = pg.password.get_secret_value()
    root_engine = create_async_engine(
        pg.root_url, echo=settings.db_echo, isolation_level="AUTOCOMMIT"
    )
    try:
        async with root_engine.begin() as root:
            with suppress(ProgrammingError):
                await root.execute(text(f"CREATE USER {user} WITH PASSWORD '{password}'"))
                logger.info(f"Created {user!r} owner")
            await root.execute(text(f"CREATE DATABASE {pg.path} OWNER {user}"))
            logger.info(f"Created '{pg.path}' database")
    except ConnectionDoesNotExistError as exc:
        raise RuntimeError(f"Failed connect to {pg.root_url}, wrong admin password?") from exc


async def create_db():
    """Create database, owner and tables (only if they do not exist)"""
    for retry in range(2):
        try:
            async with engine.begin() as conn:
                if settings.drop_db_at_start:
                    await conn.run_sync(TableBase.metadata.drop_all)
                    logger.info("DB tables dropped")
                await conn.run_sync(TableBase.metadata.create_all)
                logger.info("DB tables checked (exists or created)")
            break

        except (InvalidAuthorizationSpecificationError, ConnectionDoesNotExistError) as exc:
            if retry:
                raise RuntimeError("DB and it's USER must be created before retry") from exc
            await _create_db_and_user()
        except ConnectionRefusedError as exc:
            raise RuntimeError(f"Cannot access {settings.postgres.app_url} db: {exc!r}") from None
        except Exception as exc:
            raise RuntimeError(f"Uncaptured exception: {exc!r}\n\t{type(exc).mro()=}") from exc
    else:
        raise RuntimeError("Unexpected database engine init route")

    if settings.add_example_data:
        try:
            async with db_maker.begin() as session:
                session.add_all(get_example_data())
                logger.info("DB filled by example data")
        except IntegrityError:
            logger.error("Cannot add example data, it maybe already added")

    # Closing the engine because the async loop will also close
    await engine.dispose()
    logger.info("DB initialized")


class DBMiddleware(MiddlewareBase):
    _scope_names = ("db_exit_stack", "db")

    async def handle(self, _) -> AsyncGenerator:
        exit_stack = AsyncExitStack()
        try:
            yield exit_stack, None
        finally:
            await exit_stack.aclose()
        yield


async def get_db(request: Request) -> AsyncSession:
    """Get db only when called"""
    if db := (scope := request.scope).get("db"):
        return db

    if exit_stack := scope.get("db_exit_stack"):
        db = scope["db"] = await exit_stack.enter_async_context(db_maker.begin())
        return db

    raise RuntimeError("DBMiddleware is not initialized!")


DBDep = Annotated[AsyncSession, Depends(get_db)]  # Get db at route as dependency
