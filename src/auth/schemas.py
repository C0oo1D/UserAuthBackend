from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_core import from_json

from models import SessionDB, UserDB
from settings import settings

_name_field = partial(Field, min_length=1, max_length=50)
_pass_field = partial(Field, min_length=8, max_length=64, repr=False)

NameAn = Annotated[str, _name_field()]
NameOptAn = Annotated[str | None, _name_field(None)]

PassAn = Annotated[SecretStr, _pass_field(exclude=True)]
PassOptAn = Annotated[SecretStr, _pass_field(None, exclude=True)]


# Simple schemas
class Message(BaseModel):
    message: str


class Error(BaseModel):
    error: str


# Checkers
class _UserCheck:
    @field_validator("firstname", "lastname", "surname", mode="after")
    @classmethod
    def title(cls, value: str | None) -> str | None:
        if value:
            return value.title()
        return None


def _check_and_hash_password(field_name: str) -> Callable[[str, ValidationInfo], str]:
    def wrapper(confirm_password: str, info: ValidationInfo) -> str:
        """Check passwords match only if both passed validation, then hash password secret value
        todo: add minimum password strength validation (lower, upper, digit, special, non-ascii)"""
        if (password := info.data.get(field_name, "")) and confirm_password:
            if password != confirm_password:
                raise ValueError("Passwords do not match!")
            return settings.password_hasher.hash(password.get_secret_value())
        return confirm_password

    return wrapper


# Orm schemas
class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class UserInfo(OrmSchema):
    firstname: NameAn
    lastname: NameOptAn
    surname: NameOptAn
    email: EmailStr


class User(UserInfo):
    id: UUID
    hashed_password: str
    is_superuser: bool

    def get_info(self) -> UserInfo:
        fields = UserInfo.model_fields
        return UserInfo(**{k: v for k, v in self.model_dump().items() if k in fields})


class Session(OrmSchema):
    id: UUID
    user: User
    user_agent: str
    updated_at: datetime

    @classmethod
    def from_db(cls, session_db: SessionDB, user_db: UserDB) -> Self:
        """Model from database"""
        return cls.model_validate(session_db, context={"user": User.model_validate(user_db)})

    @classmethod
    def from_cache(cls, session_json: str, user_json: str) -> Self:
        """Model from cache"""
        return cls.model_validate(
            from_json(session_json) | {"user": User.model_validate_json(user_json)}
        )

    @field_serializer("user")
    def serialize_user(self, user: User) -> str:
        return str(user.id)


class RegisterUserForm(UserInfo, _UserCheck):
    password: PassAn
    hashed_password: Annotated[
        SecretStr,
        _pass_field(alias="confirm_password"),
        AfterValidator(_check_and_hash_password("password")),
    ]


class UpdateUserForm(OrmSchema, _UserCheck):
    password: PassAn
    firstname: NameOptAn
    lastname: NameOptAn
    surname: NameOptAn
    email: Annotated[EmailStr, Field(None)]
    new_password: PassOptAn
    hashed_password: Annotated[
        SecretStr,
        _pass_field(None, alias="confirm_new_password"),
        AfterValidator(_check_and_hash_password("new_password")),
    ]

    @model_validator(mode="after")
    def check_passwords(self):
        if self.password == self.new_password:
            raise ValueError("Unable to update password - it is identical")
        if any(pair := (self.new_password, self.hashed_password)) and not all(pair):
            raise ValueError("Fields new_password and confirm_new_password must be both or none")
        return self


class Role(OrmSchema):
    name: str
    description: str | None


class Permission(OrmSchema):
    name: str
    codename: str
    description: str | None
