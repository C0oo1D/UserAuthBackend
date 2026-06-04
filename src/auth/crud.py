from datetime import datetime
from logging import getLogger
from typing import overload, Sequence
from uuid import UUID

from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute as Col, joinedload

from models import TableBase, SessionDB, UserDB, RoleDB
from schemas import RegisterUserForm
from settings import settings, get_utc_now


logger = getLogger(__name__)


# Helper functions
def _is_table(var: UUID | TableBase) -> bool:
    match var:
        case UUID():
            return False
        case TableBase():
            return True
    logger.error(msg := f'Wrong uuid/table parameter provided: {var!r} ({type(var)})')
    raise ValueError(msg)


# Create operations
async def _create[T: TableBase](db: AsyncSession, row: T) -> T:
    db.add(row)
    await db.flush()
    return row


async def create_user_db(db: AsyncSession, user_form: RegisterUserForm, is_superuser=False
                         ) -> UserDB:
    return await _create(db, UserDB(**user_form.model_dump(), is_superuser=is_superuser))


async def create_session_db(db: AsyncSession, user_id: UUID, user_agent: str) -> SessionDB:
    return await _create((kw := locals()).pop('db'), SessionDB(**kw))


# Read single operations
async def _get_one[T: TableBase](db: AsyncSession, table: type[T] | Col, where, options=None,
                                 unique: bool = False) -> T | None:
    stmt = select(table).where(where)
    if options:
        stmt = stmt.options(options)

    result = await db.execute(stmt)

    if unique:
        result = result.unique()
    return result.scalar_one_or_none()


@overload
async def get_user_db(db: AsyncSession, email: str, *, roles=False, permissions=False
                      ) -> UserDB | None: ...
@overload
async def get_user_db(db: AsyncSession, user_id: UUID, *, roles=False, permissions=False
                      ) -> UserDB | None: ...
async def get_user_db(db: AsyncSession, var: UUID | str, *, roles=False, permissions=False
                      ) -> UserDB | None:
    field = UserDB.id if isinstance(var, UUID) else UserDB.email
    kwargs = {}
    match roles, permissions:
        case True, True:
            kwargs = {'options': joinedload(UserDB.roles).joinedload(RoleDB.permissions),
                      'unique': True}
        case True, False:
            kwargs = {'options': joinedload(UserDB.roles), 'unique': True}
        case False, True:
            raise ValueError('Cannot load permissions in UserDB without roles')
    return await _get_one(db, UserDB, field == var, **kwargs)


async def get_session_db(db: AsyncSession, session_id: UUID) -> SessionDB | None:
    return await _get_one(db, SessionDB, SessionDB.id == session_id)


async def get_count_db(db: AsyncSession, table: type[TableBase]) -> int:
    return await db.scalar(select(func.count()).select_from(table))


async def get_role_db(db: AsyncSession, name: str, *, permissions=False) -> RoleDB | None:
    options = joinedload(RoleDB.permissions) if permissions else None
    return await _get_one(db, RoleDB, RoleDB.name == name, options=options)


# Read multiple operations
@overload
async def _get_many[T: TableBase, C](db: AsyncSession, table_col: type[T], where=None, *,
                                     order_by=None, options=None, offset: int = 0, limit: int = 10,
                                     unique: bool = False) -> Sequence[T]: ...
@overload
async def _get_many[T: TableBase, C](db: AsyncSession, table_col: Col[C], where=None, *,
                                     order_by=None, options=None, offset: int = 0, limit: int = 10,
                                     unique: bool = False) -> Sequence[C]: ...
async def _get_many[T: TableBase, C](db: AsyncSession, table_col: type[T] | Col[C], where=None, *,
                                     order_by=None, options=None, offset: int = 0, limit: int = 10,
                                     unique: bool = False) -> Sequence[T] | Sequence[C]:
    stmt = select(table_col)
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    if where is not None:
        stmt = stmt.where(where)
    if options:
        stmt = stmt.options(options)
    if offset:
        stmt = stmt.offset(offset)
    if limit:
        stmt = stmt.limit(limit)

    result = await db.execute(stmt)

    if unique:
        result = result.unique()
    return result.scalars().all()


async def get_roles_db(db: AsyncSession, *, permissions=False, **kwargs):
    if permissions:
        if "options" in kwargs or "unique" in kwargs:
            raise ValueError("Cannot use options or unique when permissions used")
        kwargs |= {"options": joinedload(RoleDB.permissions), "unique": True}
    return await _get_many(db, RoleDB, **kwargs)


# Update operations
async def update_user_db(db: AsyncSession, user_id: UUID, **kwargs):
    await db.execute(update(UserDB).where(UserDB.id == user_id).values(**kwargs))
    await db.flush()


@overload
async def update_session_db(db: AsyncSession, session_id: UUID, updated_at: datetime, **kwargs): ...
@overload
async def update_session_db(db: AsyncSession, session: SessionDB, updated_at: datetime): ...
async def update_session_db(db: AsyncSession, var: UUID | SessionDB,
                            updated_at: datetime | None = None, **kwargs):
    if _is_table(var):
        var.updated_at = updated_at or get_utc_now()
    else:
        kwargs |= {'updated_at': updated_at or get_utc_now()}
        await db.execute(update(SessionDB).where(SessionDB.id == var).values(**kwargs))
    await db.flush()


async def suspend_user_db(db: AsyncSession, user: UserDB):
    user.is_active = False
    await db.flush()


# Delete operations
async def delete_session_db(db: AsyncSession, session_id: UUID):
    await db.execute(delete(SessionDB).where(SessionDB.id == session_id))
    await db.flush()


async def delete_sessions_db(db: AsyncSession, user_id: UUID):
    await db.execute(delete(SessionDB).where(SessionDB.user_id == user_id))
    await db.flush()


# Security operations
def _check_password(hashed_password: str, password: str) -> str | None:
    """Returns None at wrong password or new hash for password if rehash needed, else empty str"""
    try:
        password_hasher = settings.password_hasher
        password_hasher.verify(hashed_password, password)
        if password_hasher.check_needs_rehash(hashed_password):
            return password_hasher.hash(password)
        return ''
    except VerifyMismatchError:
        return None


async def authenticate_user_db(db: AsyncSession, email: str, password: str) -> UserDB | None:
    if user := await get_user_db(db, email):
        if (rehashed := _check_password(str(user.hashed_password), password)) is not None:
            if rehashed:
                user.hashed_password = rehashed
                await db.flush()
                logger.info(f'Rehashed {user} password')
            return user
    return None


async def assign_role_db(db: AsyncSession, user_id: UUID, role_name: str):
    user = await _get_one(db, UserDB, UserDB.id == user_id)
    if not user:
        return None

    role = await _get_one(db, RoleDB, RoleDB.name == role_name)
    if not role:
        return None

    if role not in user.roles:
        user.roles.append(role)
        await db.commit()
        await db.refresh(user)
    return user
