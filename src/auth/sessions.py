from datetime import datetime, timedelta
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import Request, Response, Depends, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from crud import get_session_db, update_session_db, delete_session_db, get_user_db
from database import get_db
from schemas import CacheItem, User, Session
from settings import get_utc_now, session_cache_expire, session_expire, secure_cookie


logger = getLogger(__name__)

_cookie_name = 'session_id'
_del_cookie_params = {'httponly': True, 'secure': secure_cookie, 'samesite': "strict"}
_set_cookie_params = _del_cookie_params | {'max_age': int(timedelta(days=365).total_seconds())}


def is_valid(item: datetime, expire: timedelta) -> datetime | None:
    return now if (now := get_utc_now()) - item < expire else None


def set_cookie(response: Response, session_id: str):
    response.set_cookie(_cookie_name, session_id, **_set_cookie_params)


def del_cookie(response: Response):
    response.delete_cookie(_cookie_name, **_del_cookie_params)


def _create_session_middleware():
    """Create function wrapper needed only for linter passing, some FastAPI undocumented issue?
    todo: combine with starlette AuthenticationBackend and sessions for correct usage
    todo: cache cleaner must be realized through background tasks"""
    class Cache(dict[str, CacheItem]):
        def delete_session(self, session: Session):
            try:
                self.pop(str(session.id))
            except KeyError:
                raise KeyError(f'Cannot find {str(session.id)} in cache, but it must be')

        def update_user(self, user: User):
            user_id = user.id
            for v in self.values():
                if v.user.id == user_id:
                    v.user = user

        def delete_user(self, user: User):
            user_id = user.id
            for k, v in dict(self).items():
                if v.user.id == user_id:
                    del self[k]


    class _SessionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
            # Fill user and session in request
            request.scope |= {'user': None, 'session': {}}
            self.process_cache()
            delete_cookie = not await self.process_session(request)

            # Next middlewares handling
            response = await call_next(request)

            # Remove session from cookies if checks not passed
            if delete_cookie:
                del_cookie(response)
            return response

        @staticmethod
        def process_cache():
            """Handling LRU cache items in reversed order by its validity time"""
            for session_id, item in dict(cache).items():
                if is_valid(item.session.updated_at, session_cache_expire):
                    break
                cache.pop(session_id)

        @staticmethod
        async def process_session(request: Request) -> bool:
            if not (session_id_str := request.cookies.get(_cookie_name)):
                return True

            # Get session from reversed LRU cache
            if item := cache.pop(session_id_str, None):
                item.update()
                request.scope |= {"user": item.user, "session": {session_id_str: item.session}}
                cache[session_id_str] = item
                return True

            db = await get_db(request)

            if not (session_db := await get_session_db(db, session_id := UUID(session_id_str))):
                return False

            if not (now := is_valid(session_db.updated_at, session_expire)):  # noqa sqlalchemy Mapped linter bug
                await delete_session_db(db, session_id)
                return False

            await update_session_db(db, session_db, now)

            if not (user_db := await get_user_db(db, session_db.user_id)):  # noqa sqlalchemy Mapped linter bug
                logger.error(f"{session_db=!r} has no valid user, deleting session")
                await delete_session_db(db, session_id)
                return False

            if not user_db.is_active:
                logger.error(f"{user_db=!r} was suspended, deleting session")
                await delete_session_db(db, session_id)
                return False

            user, session = User.model_validate(user_db), Session.model_validate(session_db)
            cache[session_id_str] = CacheItem(user=user, session=session)
            request.scope |= {'user': user, 'session': {session_id_str: session}}
            return True

    return Cache(), _SessionMiddleware


def get_user(request: Request) -> User:
    if user := request.user:
        return user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED)


def get_session(request: Request) -> Session:
    if session := request.session:
        return tuple(session.values())[0]  # noqa pycharm linter bug
    raise HTTPException(status.HTTP_401_UNAUTHORIZED)


UserDep = Annotated[User, Depends(get_user)]
SessionDep = Annotated[Session, Depends(get_session)]

cache, SessionMiddleware = _create_session_middleware()
