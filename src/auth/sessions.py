from asyncio import CancelledError, create_task, sleep
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response, status

from cache import get_cache
from crud import (
    delete_session_db,
    get_session_db,
    get_user_db,
    update_session_db,
    update_sessions_db,
)
from database import db_maker, get_db
from middleware import MiddlewareBase
from schemas import Session, User
from settings import get_utc_now, settings

logger = getLogger(__name__)

_cookie_name = "session_id"
_del_cookie_params = {"httponly": True, "secure": settings.secure_cookie, "samesite": "strict"}
_set_cookie_params = _del_cookie_params | {"max_age": int(timedelta(days=365).total_seconds())}
db_pending: dict[Session, datetime] = {}


def is_valid(item: datetime, expire: timedelta) -> datetime | None:
    return now if (now := get_utc_now()) - item < expire else None


def set_cookie(response: Response, session_id: str):
    response.set_cookie(_cookie_name, session_id, **_set_cookie_params)


def del_cookie(response: Response):
    response.delete_cookie(_cookie_name, **_del_cookie_params)


@asynccontextmanager
async def session_lifespan(_):
    """Send accumulated session updates to db each minute"""

    async def db_filling():
        data = dict(db_pending)
        db_pending.clear()
        async with db_maker.begin() as db:
            await update_sessions_db(db, data)

    async def db_filling_handler():
        try:
            while True:
                [await sleep(1) for _ in range(60)]
                if db_pending:
                    await db_filling()
        except CancelledError:
            pass
        finally:
            await db_filling()

    task = create_task(db_filling_handler())
    yield
    task.cancel()


class SessionMiddleware(MiddlewareBase):
    """todo: combine with starlette AuthenticationBackend and sessions for correct usage"""

    _scope_names = ("session", "user")

    async def handle(
        self, request: Request
    ) -> AsyncGenerator[tuple[dict[str, Session], User], Response]:
        # Fill user and session in request
        delete_cookie, data = await self.process_session(request)

        # Handle request
        response = yield data or ({}, None)

        # Remove session from cookies if checks not passed and new cookie is not set
        if delete_cookie and not response.headers.get("set-cookie"):
            del_cookie(response)
        yield

    @staticmethod
    async def process_session(
        request: Request,
    ) -> tuple[bool, tuple[dict[str, Session], User] | None]:
        # Return without session
        if not (session_id_str := request.cookies.get(_cookie_name)):
            return False, None

        # Return session from cache
        cache = get_cache(request)
        if session := await cache.get(session_id_str):
            session.updated_at = now = get_utc_now()
            db_pending[session.id] = {"updated_at": now}
            return False, ({session_id_str: session}, session.user)

        # Open db instance
        db = await get_db(request)

        # Delete session cookie if it is not in db
        if not (session_db := await get_session_db(db, session_id := UUID(session_id_str))):
            return True, None

        # Delete session cookie if it is not valid
        if not (now := is_valid(session_db.updated_at, settings.session_expire)):
            await delete_session_db(db, session_id)
            return True, None

        # Update session.updated_at in db
        await update_session_db(db, session_db, now)

        # Delete session cookie if user is not exists
        if not (user_db := await get_user_db(db, session_db.user_id)):
            logger.error(f"Session {session_db.id=!r} has no valid user, deleting session")
            await delete_session_db(db, session_id)
            return True, None

        # Delete session cookie if user is suspended
        if not user_db.is_active:
            logger.error(f"User {user_db.id=!r} was suspended, deleting session")
            await delete_session_db(db, session_id)
            return True, None

        # Update cache and return session from db
        await cache.set(session := Session.from_db(session_db, user_db))
        return False, ({session_id_str: session}, session.user)


def get_user(request: Request) -> User:
    if user := request.user:
        return user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED)


def get_session(request: Request) -> Session:
    if session := request.session:
        return next(iter(session.values()))
    raise HTTPException(status.HTTP_401_UNAUTHORIZED)


UserDep = Annotated[User, Depends(get_user)]
SessionDep = Annotated[Session, Depends(get_session)]
