from contextlib import AsyncExitStack
from logging import getLogger
from typing import Annotated

from fastapi import Request, Response, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from models import TableBase, PermissionDB, RoleDB, UserDB
from settings import settings


logger = getLogger(__name__)


engine = create_async_engine(settings.db_url.get_secret_value(), echo=settings.db_echo)
db_maker = async_sessionmaker(engine, autoflush=False)


def get_test_data():
    p_gr = PermissionDB(name='Get roles', codename='get_roles',
                       description='Allows get roles list with permissions')
    p_ar = PermissionDB(name='Assign roles', codename='assign_roles',
                       description='Allows assign roles for users')

    r_adm = RoleDB(name='Administrator',
                   description='Have all permissions, cannot access superuser endpoints')
    r_adm.permissions.extend((p_gr, p_ar))

    r_mod = RoleDB(name='Moderator', description='Can see permissions')
    r_mod.permissions.append(p_gr)

    hasher = settings.password_hasher.hash

    u_su = UserDB(email='admin@example.com', firstname='Admin', is_superuser=True,
                  hashed_password=hasher('su_password'))

    u_adm = UserDB(email='i_am_admin@example.com', firstname='i am admin', lastname='or not',
                   hashed_password=hasher('adm_password'))
    u_adm.roles.extend((r_mod, r_adm))

    u_mod = UserDB(email='moder@example.com', firstname='moder', surname='what a sur',
                   hashed_password=hasher('mod_password'))
    u_mod.roles.append(r_mod)

    u_std = UserDB(email='stduser@example.com', firstname='filippo',
                   hashed_password=hasher('std_password'))

    return [p_gr, p_ar, r_adm, r_mod, u_su, u_adm, u_mod, u_std]


async def create_db_lifespan(_):
    async with engine.begin() as conn:
        if settings.drop_db_at_start:
            await conn.run_sync(TableBase.metadata.drop_all)
        await conn.run_sync(TableBase.metadata.create_all)

    if settings.add_test_data:
        try:
            async with db_maker.begin() as session:
                session.add_all(get_test_data())
        except IntegrityError:
            logger.error("Cannot add test data, it maybe already added")
    yield


def _create_db_middleware():
    """Create function wrapper needed only for linter passing, some FastAPI undocumented issue?"""

    class _DBMiddleware(BaseHTTPMiddleware):
        """todo: add __init__ with params"""
        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
            exit_stack = AsyncExitStack()
            request.scope['db_exit_stack'] = exit_stack
            request.scope['db'] = None

            try:
                response = await call_next(request)
            finally:
                await exit_stack.aclose()
            return response

    return _DBMiddleware


async def get_db(request: Request) -> AsyncSession:
    """Get db only when called"""
    scope = request.scope
    if db := scope.get('db'):
        return db

    if not (exit_stack := scope.get('db_exit_stack')):
        raise RuntimeError('DB Middleware is not initialized!')

    db = scope['db'] = await exit_stack.enter_async_context(db_maker.begin())
    return db


DBDep = Annotated[AsyncSession, Depends(get_db)]  # Get db at route as dependency

DBMiddleware = _create_db_middleware()
