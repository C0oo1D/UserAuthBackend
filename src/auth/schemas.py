from datetime import datetime
from functools import partial
from typing import Annotated, Callable
from uuid import UUID

from pydantic import (BaseModel, ConfigDict, Field, EmailStr, ValidationInfo, SecretStr,
                      field_validator, AfterValidator, model_validator)

from settings import password_hasher, get_utc_now


_name_field = partial(Field, min_length=1, max_length=50)
_pass_field = partial(Field, min_length=8, max_length=64, repr=False)

NameAn = Annotated[str, _name_field()]
NameOptAn = Annotated[str | None, _name_field(None)]

PassAn = Annotated[SecretStr, _pass_field(exclude=True)]
PassOptAn = Annotated[SecretStr, _pass_field(None, exclude=True)]


# Simple schemas
class CacheItem(BaseModel):
    user: 'User'
    session: 'Session'

    def update(self):
        self.session.updated_at = get_utc_now()


class Message(BaseModel):
    message: str


class Error(BaseModel):
    error: str


# Checkers
class _UserCheck:
    @field_validator("firstname", "lastname", "surname", mode="after")  # noqa pycharm linter bug
    @classmethod
    def title(cls, value: str | None) -> str | None:
        if value:
            return value.title()
        return None


def _check_and_hash_password(field_name: str) -> Callable[[str, ValidationInfo], str]:
    def wrapper(confirm_password: str, info: ValidationInfo) -> str:
        """Check passwords match only if both passed validation, then hash password secret value
        todo: add minimum password strength validation (lower, upper, digit, special, non-ascii)"""
        if (password := info.data.get(field_name)) and confirm_password:
            if password != confirm_password:
                raise ValueError('Passwords do not match!')
            return password_hasher.hash(password.get_secret_value())  # noqa pycharm linter bug
        return confirm_password
    return wrapper


# Orm schemas
class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra='forbid')


class Session(OrmSchema):
    id: UUID
    user_id: UUID
    user_agent: str
    updated_at: datetime


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


class RegisterUserForm(UserInfo, _UserCheck):
    password: PassAn
    hashed_password: Annotated[SecretStr, _pass_field(alias='confirm_password'),
                               AfterValidator(_check_and_hash_password('password'))]


class UpdateUserForm(OrmSchema, _UserCheck):
    password: PassAn
    firstname: NameOptAn
    lastname: NameOptAn
    surname: NameOptAn
    email: Annotated[EmailStr, Field(None)]
    new_password: PassOptAn
    hashed_password: Annotated[SecretStr, _pass_field(None, alias='confirm_new_password'),
                               AfterValidator(_check_and_hash_password('new_password'))]

    @model_validator(mode='after')  # noqa pycharm linter bug
    def check_passwords_filled(self):
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
