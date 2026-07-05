from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from logging import getLogger
from typing import Annotated

from asyncpg import ConnectionDoesNotExistError, InvalidAuthorizationSpecificationError
from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from middleware import MiddlewareBase
from models import PermissionDB, RoleDB, TableBase, UserDB
from settings import settings

logger = getLogger(__name__)


engine = create_async_engine(settings.postgres.app_url, echo=settings.db_echo)
db_maker = async_sessionmaker(engine, autoflush=False)


def get_test_data():
    p_gr = PermissionDB(
        name="Get roles",
        codename="get_roles",
        description="Allows get roles list with permissions",
    )
    p_ar = PermissionDB(
        name="Assign roles", codename="assign_roles", description="Allows assign roles for users"
    )

    r_adm = RoleDB(
        name="Administrator", description="Has all permissions, cannot access superuser endpoints"
    )
    r_adm.permissions.extend((p_gr, p_ar))

    r_mod = RoleDB(name="Moderator", description="Can see permissions")
    r_mod.permissions.append(p_gr)

    hasher = settings.password_hasher.hash

    u_su = UserDB(
        email="admin@example.com",
        firstname="Admin",
        is_superuser=True,
        hashed_password=hasher("su_password"),
    )

    u_adm = UserDB(
        email="i_am_admin@example.com",
        firstname="i am admin",
        lastname="or not",
        hashed_password=hasher("adm_password"),
    )
    u_adm.roles.extend((r_mod, r_adm))

    u_mod = UserDB(
        email="moder@example.com",
        firstname="moder",
        surname="what a sur",
        hashed_password=hasher("mod_password"),
    )
    u_mod.roles.append(r_mod)

    u_std = UserDB(
        email="stduser@example.com", firstname="filippo", hashed_password=hasher("std_password")
    )

    return [p_gr, p_ar, r_adm, r_mod, u_su, u_adm, u_mod, u_std]


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


@asynccontextmanager
async def create_db_lifespan(_):
    """Create database, owner and tables (only if they do not exist)"""
    for retry in range(2):
        try:
            async with engine.begin() as conn:
                if settings.drop_db_at_start:
                    await conn.run_sync(TableBase.metadata.drop_all)
                await conn.run_sync(TableBase.metadata.create_all)
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

    if settings.add_test_data:
        try:
            async with db_maker.begin() as session:
                session.add_all(get_test_data())
        except IntegrityError:
            logger.error("Cannot add test data, it maybe already added")
    yield


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
