from contextlib import AbstractAsyncContextManager
from typing import Annotated, ClassVar
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from pydantic_core import from_json
from redis.asyncio import Redis
from sqlalchemy.engine.url import URL

from schemas import Session, User
from settings import settings


class CacheBase(AbstractAsyncContextManager):
    _url: URL = settings.redis.app_url
    state_name: ClassVar[str]
    _redis: Redis

    def __init__(self, app: FastAPI):
        """Simulate Callable[[FastAPI], AbstractAsyncContextManager] on class itself"""
        super().__init__()
        app.state[self.state_name] = self

    async def __aenter__(self):
        if redis := self.__dict__.get("_redis"):
            return await redis.__aenter__()

        redis = Redis.from_url(
            self._url.render_as_string(hide_password=False), decode_responses=True
        )
        if not await redis.ping():
            await redis.aclose()
            raise RuntimeError(f"Redis connection to {self._url!r} failed")

        self._redis = redis
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._redis.__aexit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name: str):
        if name == "_redis":
            raise RuntimeError("Redis connection is not established")
        return object.__getattribute__(self, name)

    async def hash_get(self, name: str, key: str) -> str | None:
        return await self._redis.hget(name, key)

    async def hash_set(self, name: str, key: str, value: str, ttl: int) -> int:
        return await self._redis.hsetex(name, key, value, ex=ttl)

    async def hash_del(self, name: str, key: str) -> int:
        return await self._redis.hdel(name, key)


class Cache(CacheBase):
    """todo: Research client-side caching (CSC) possibility with asyncio redis in current config"""

    _name_uname_validate_dump_udump_ttl = (
        Session.__name__,
        User.__name__,
        Session.from_cache,
        Session.model_dump_json,
        User.model_dump_json,
        int(settings.session_cache_expire.total_seconds()),
    )
    state_name = "cache"
    session_user: dict[str, str]

    async def __aenter__(self):
        """Reload session-user id's mapping at init for atomic access to redis cached data"""
        await super().__aenter__()
        name, uname, *_ = self._name_uname_validate_dump_udump_ttl
        if settings.drop_db_at_start:
            await self._redis.delete(name, uname)
            session_user = {}
        else:
            session_user = await self.get_all_pairs()
        self.session_user = session_user
        return self

    async def get(self, key: UUID | str) -> Session | None:
        if not (user_key := self.session_user.get(key := str(key))):
            return None

        name, uname, validate, *_ = self._name_uname_validate_dump_udump_ttl
        async with self._redis.pipeline() as pipe:
            session, user = await pipe.hget(name, key).hget(uname, user_key).execute()

        if session and user:
            return validate(session, user)
        return None

    async def get_all_pairs(self) -> dict[str, str]:
        sessions = await self._redis.hgetall(self._name_uname_validate_dump_udump_ttl[0])
        return {k: from_json(v)["user"] for k, v in sessions.items()}

    async def set(self, session: Session) -> int:
        name, uname, _, dump, udump, ttl = self._name_uname_validate_dump_udump_ttl
        async with self._redis.pipeline() as pipe:
            sid, uid = str(session.id), str(session.user.id)
            written, _ = (
                await pipe.hsetex(name, sid, dump(session), ex=ttl)
                .hsetex(uname, uid, udump(session.user), ex=ttl)
                .execute()
            )
        self.session_user[sid] = uid
        return written

    async def delete(self, session: Session) -> int:
        name, *_ = self._name_uname_validate_dump_udump_ttl
        return await self.hash_del(name, str(session.id))

    async def update_user(self, user: User) -> int:
        _, uname, *_, udump, ttl = self._name_uname_validate_dump_udump_ttl
        return await self.hash_set(uname, str(user.id), udump(user), ttl)

    async def delete_user(self, user: User) -> int:
        uid = str(user.id)
        name, uname, *_ = self._name_uname_validate_dump_udump_ttl
        sessions = [k for k, v in (await self.get_all_pairs()).items() if v == uid]
        async with self._redis.pipeline() as pipe:
            deleted, _ = await pipe.hdel(name, *sessions).hdel(uname, uid).execute()
        pop = self.session_user.pop
        [pop(key) for key in sessions]
        return deleted


def get_cache(request: Request) -> Cache:
    try:
        return request.app.state[Cache.state_name]
    except KeyError:
        raise RuntimeError("Cache is not initialized at lifespan!") from None


CacheDep = Annotated[Cache, Depends(get_cache)]
