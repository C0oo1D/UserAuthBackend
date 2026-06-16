from datetime import UTC, datetime, timedelta
from functools import cached_property, partial
from pathlib import Path
from typing import Annotated

from argon2 import PasswordHasher
from pydantic import BaseModel, Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

app_name = Path(__file__).parent.name
get_utc_now = partial(datetime.now, tz=UTC)  # sqlalchemy.func.utcnow() fails in asyncpg
PassHasherAn = Annotated[PasswordHasher, Field(alias="password_hasher_kw", default_factory=dict)]


class PostgresSettings(BaseModel):
    password: SecretStr
    app_user: str = app_name
    app_password: SecretStr
    hosts: tuple[str, ...] = ("localhost",)
    db_name: str = app_name

    @model_validator(mode="after")
    def verify(self):
        if self.app_password and not self.app_user:
            raise AssertionError("App user must be provided when app password provided")
        return self

    def _hosts(self) -> tuple[str | None, int | None, tuple[str, ...]]:
        split = partial(str.rsplit, sep=":", maxsplit=1)

        if len(hosts := self.hosts) == 1:
            host_data = split(hosts[0])
            host, port = (hosts[0], None) if len(host_data) == 1 else host_data
            return host, port, ()

        gen = (f"{y[0]}:{y[1] if len(y) == 2 else '5432'}" for x in hosts if (y := split(x)))
        return None, None, tuple(gen)

    def _url(
        self,
        *,
        driver: str = "postgresql+asyncpg",
        user: str | None = None,
        password: SecretStr | None = None,
        db: str | None = None,
    ) -> URL:
        user = user or self.app_user
        password = password or self.app_password
        if password:
            password = password.get_secret_value()
        host, port, query = self._hosts()
        db = db or self.db_name
        return URL.create(driver, user, password, host, port, db, query)

    @cached_property
    def app_url(self) -> URL:
        return self._url()

    @cached_property
    def root_url(self) -> URL:
        return self._url(user="postgres", password=self.password, db="postgres")

    @cached_property
    def test_url(self) -> URL:
        return self._url(driver="postgresql")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="_", env_nested_max_split=1, extra="forbid"
    )

    postgres: PostgresSettings
    password_hasher: PassHasherAn
    session_expire: Annotated[timedelta, Field(alias="session_expire_kw", default={"days": 14})]
    session_cache_expire: Annotated[
        timedelta, Field(alias="session_cache_expire_kw", default={"hours": 6})
    ]
    host: str = "localhost"
    port: int = 80
    db_echo: bool = False
    secure_cookie: bool = True
    debug: bool = False
    drop_db_at_start: bool = False
    add_test_data: bool = False

    @field_validator("*", mode="before")
    @classmethod
    def parse_kw(cls, value, info: ValidationInfo):
        """Parse keyword arguments and pass them to the target type initializer (if not dict)"""
        field_name = str(info.field_name)  # Attached to model fields, there is no None possible
        field = cls.__pydantic_fields__[field_name]
        if (alias := field.alias) and alias.endswith("_kw") and not field_name.endswith("_kw"):
            value = field.annotation(**value)
        return value


# noinspection PyArgumentList
settings = Settings()
