from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from settings import get_utc_now


class TableBase(DeclarativeBase):
    pass


# Many-to-Many tables
user_roles = Table(
    "user_roles",
    TableBase.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)


role_permissions = Table(
    "role_permissions",
    TableBase.metadata,
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id"), primary_key=True),
)


# Main tables
class UserDB(TableBase):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    firstname: Mapped[str]
    lastname: Mapped[str | None]
    surname: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)
    hashed_password: Mapped[str]

    roles: Mapped[list["RoleDB"]] = relationship(secondary=user_roles, back_populates="users")
    sessions: Mapped[list["SessionDB"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class SessionDB(TableBase):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    user_agent: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    user: Mapped["UserDB"] = relationship(back_populates="sessions")


class RoleDB(TableBase):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None]

    users: Mapped[list["UserDB"]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[list["PermissionDB"]] = relationship(
        secondary=role_permissions, back_populates="roles"
    )


class PermissionDB(TableBase):
    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(unique=True)
    codename: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None]

    roles: Mapped[list["RoleDB"]] = relationship(
        secondary=role_permissions, back_populates="permissions"
    )
