from datetime import UTC, datetime, timedelta
from functools import cached_property, partial
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote, quote_plus

from argon2 import PasswordHasher
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, util
from uvicorn import Config

app_name = Path(__file__).parent.name
get_utc_now = partial(datetime.now, tz=UTC)  # sqlalchemy.func.utcnow() fails in asyncpg

type query_dict = dict[str, str | tuple[str, ...]]
type query_tuple = tuple[tuple[str, str], ...]
type query_t = query_dict | query_tuple


def opt_an[T: type](cls: T):
    """Annotated optional type with default factory if not provided"""
    return Annotated[cls, Field(default_factory=cls)]


def get_field(cls: type[BaseModel], info: ValidationInfo) -> tuple[str, FieldInfo]:
    """Get field name and info at validation"""
    return (field_name := str(info.field_name)), cls.__pydantic_fields__[field_name]


class MultihostURL(URL):
    """Added non RFC-3986 multihost in authority"""

    def format_multihost(self, multihost: str) -> str:
        hosts, port = [], self.port
        for item in multihost.split(","):
            # IPv6
            if item.count(":") > 1:
                if item.endswith("]"):
                    item = f"{item}:{port}" if port else item
                elif (i := item.rfind("]")) >= 0:
                    if not item[i + 1 :].startswith(":"):
                        raise ValueError(f"Wrong multihost {item=!r}")
                else:
                    item = f"[{item}]" + (f":{port}" if port else "")
            # Other
            else:
                item_host, *left = item.rsplit(":", maxsplit=1)
                if not left and port:
                    item = f"{item_host}:{port}"
            hosts.append(item)
        return ",".join(hosts)

    def render_as_string(self, hide_password: bool = True) -> str:  # noqa: FBT001, FBT002
        s = self.drivername + "://"
        if self.username is not None:
            s += quote(self.username, safe=" +")
            if self.password is not None:
                s += ":" + ("***" if hide_password else quote(str(self.password), safe=" +"))
            s += "@"
        port = self.port
        if (host := self.host) is not None:
            if "," in host:
                port = None
                s += self.format_multihost(host)
            elif ":" in host:
                s += f"[{host}]"
            else:
                s += host
        if port is not None:
            s += ":" + str(self.port)
        if self.database is not None:
            s += "/" + self.database
        if self.query:
            keys = list(self.query)
            keys.sort()
            s += "?" + "&".join(
                f"{quote_plus(k)}={quote_plus(element)}"
                for k in keys
                for element in util.to_list(self.query[k])
            )
        return s


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtraModel(StrictModel):
    """Default extra="allow" is not validating fields (for example int is parsed as str)"""

    extra_kw: Annotated[dict[str, Any], Field(exclude=True, default={})]

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump() | self.extra_kw

    @model_validator(mode="after")
    def verify(self):
        if wrong := set(self.__pydantic_fields__) & set(self.extra_kw):
            cls_name = type(self).__name__
            raise ValueError(f"Field {cls_name}.extra_kw has exists fields: {', '.join(wrong)}")
        return self


class UrlBase(StrictModel):
    """Base settings model for urls
    Hidden parameters can be filled only at subclassing, other - subclassing (as default) and init
    :param _multihost_place: place for multihost, if available
    :param _multihost_default_port: default multihost port - when required, but not provided
    :param _multihost_query_field_name: field name used for providing multihost in query
    :param _multihost_raw: filled at model verify, if multihost used
    """

    _multihost_place: Literal["authority", "query"] | None = None
    _multihost_default_port: int | None = None
    _multihost_query_field_name: str = "host"
    _multihost_raw: tuple[str | None, None, query_tuple]  # host, port, query
    scheme: str = "https"
    user: str | None = None
    password: SecretStr | None = None
    host: str | None = "localhost"
    port: int | None = None
    hosts: tuple[str, ...] = ()
    path: str | None = None
    query: query_t = ()

    @property
    def _fmt_multihost(self) -> tuple[str, ...]:
        add = f":{port}" if (port := self.port or self._multihost_default_port) else ""
        return tuple(x if ":" in x else (x + add) for x in self.hosts)

    @model_validator(mode="after")
    def verify(self):
        hosts = self.hosts
        if self.password and not self.user:
            raise AssertionError("User must be provided when providing password")
        if hosts and self.host != self.__pydantic_fields__["host"].default:
            raise AssertionError("Cannot use hosts when host provided")
        if hosts and not self._multihost_place:
            raise AssertionError("Cannot use hosts when multihost is not supported")

        match len(hosts), self._multihost_place:
            case 0, _:
                pass
            case 1, _:
                self.hosts = ()
                self.host, *port_provided = hosts[0].rsplit(":", maxsplit=1)
                if port_provided:
                    self.port = int(port_provided[0])
            case _, "authority":
                self._multihost_raw = ",".join(self._fmt_multihost), None, ()
            case _, "query":
                host_key = self._multihost_query_field_name
                self._multihost_raw = None, None, tuple((host_key, x) for x in self._fmt_multihost)
            case _:
                raise ValueError(f"Wrong multihost place provided: {self._multihost_place!r}")

        return self

    def _url(
        self,
        *,
        scheme: str | None = None,
        user: str | None = None,
        password: SecretStr | None = None,
        path: str | None = None,
        query: query_t | None = None,
    ) -> URL:
        scheme, user, password, path, query = (
            getattr(self, k) if v is None else v for k, v in locals().items() if k != "self"
        )
        if password:
            password = password.get_secret_value()
        host, port, model_query = self._multihost_raw if self.hosts else (self.host, self.port, ())
        url = MultihostURL.create(scheme, user, password, host, port, path)
        return url.update_query_pairs(model_query + query)

    @cached_property
    def app_url(self) -> URL:
        return self._url()


class PostgresSettings(UrlBase):
    _multihost_place = "query"
    _multihost_default_port = 5432
    scheme: str = "postgresql+asyncpg"
    user: str = app_name
    password: SecretStr
    path: str = app_name
    root_password: SecretStr

    @cached_property
    def root_url(self) -> URL:
        return self._url(user="postgres", password=self.root_password, path="postgres")

    @cached_property
    def test_url(self) -> URL:
        return self._url(scheme="postgresql")


class RedisSettings(UrlBase):
    scheme: str = "redis"


class LogSettings(StrictModel):
    """Defaults always provided, use JSON string '{"level": null}' to disable specified log"""

    console_kw: dict = {"level": "INFO", "enqueue": True}
    file_kw: dict = {
        "level": "DEBUG",
        "enqueue": True,
        "rotation": "00:00",
        "retention": "3 month",
        "compression": "gz",
        "serialize": True,
    }

    @field_validator("*", mode="before")
    @classmethod
    def merge_with_default(cls, value, info: ValidationInfo):
        return get_field(cls, info)[1].default | (value or {})


class ServerSettings(ExtraModel):
    host: str = "localhost"
    port: int = 80
    workers: int | None = None
    access_log: bool = False

    def model_post_init(self, _):
        """Load config after init (initialize uvicorn logging handlers for loguru intercept)"""
        return self.config

    @cached_property
    def config(self) -> Config:
        return Config("app:app", **self.as_dict())

    @cached_property
    def config_tests(self):
        """NOTE: Tests is not runnable with uvicorn workers (at least for now)"""
        kwargs = self.as_dict()
        kwargs.pop("workers", None)
        return Config("app:app", **kwargs)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="_", env_nested_max_split=1, extra="forbid"
    )

    postgres: PostgresSettings
    redis: opt_an(RedisSettings)
    password_hasher: Annotated[PasswordHasher, Field(alias="password_hasher_kw", default={})]
    session_expire: Annotated[timedelta, Field(alias="session_expire_kw", default={"days": 14})]
    session_cache_expire: Annotated[
        timedelta, Field(alias="session_cache_expire_kw", default={"hours": 6})
    ]
    log: opt_an(LogSettings)
    server: opt_an(ServerSettings)
    db_echo: bool = False
    secure_cookie: bool = True
    drop_db_at_start: bool = False
    add_example_data: bool = False

    @field_validator("*", mode="before")
    @classmethod
    def parse_kw(cls, value, info: ValidationInfo):
        """Parse keyword arguments and pass them to the target type initializer"""
        field_name, field = get_field(cls, info)
        if (alias := field.alias) and alias.endswith("_kw") and not field_name.endswith("_kw"):
            value = field.annotation(**value)
        return value


# noinspection PyArgumentList
settings = Settings()
