from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Annotated

from argon2 import PasswordHasher
from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

get_utc_now = partial(datetime.now, tz=UTC)  # sqlalchemy.func.utcnow() fails in asyncpg
PassHasherAn = Annotated[PasswordHasher, Field(alias="password_hasher_kw", default_factory=dict)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="forbid")

    db_url: SecretStr
    password_hasher: PassHasherAn
    session_expire: Annotated[timedelta, Field(alias="session_expire_kw", default={"days": 14})]
    session_cache_expire: Annotated[
        timedelta, Field(alias="session_cache_expire_kw", default={"hours": 6})
    ]
    db_echo: bool = False
    secure_cookie: bool = True
    debug: bool = False
    drop_db_at_start: bool = False
    add_test_data: bool = False

    @field_validator("*", mode="before")
    @classmethod
    def parse_kw(cls, value, info: ValidationInfo):
        field_name = str(info.field_name)  # Attached to model fields, there is no None possible
        field = cls.__pydantic_fields__[field_name]
        if (alias := field.alias) and alias.endswith("_kw") and not field_name.endswith("_kw"):
            value = field.annotation(**value)
        return value


# noinspection PyArgumentList
settings = Settings()
