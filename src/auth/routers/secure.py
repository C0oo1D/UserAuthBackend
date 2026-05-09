from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import EmailStr

from crud import get_count_db, get_user_db, get_role_db, get_roles_db
from database import DBDep
from models import UserDB, SessionDB, TableBase
from permissions import permission
from schemas import Message, Role, Permission, OrmSchema


router = APIRouter(prefix="/secure")


@router.get("/admin", tags=["Admin"], response_model=Message,
            dependencies=[permission()])
async def admin(db: DBDep):
    return Message(message=f"You are admin! "
                           f"DB has {await get_count_db(db, UserDB)} users, "
                           f"and {await get_count_db(db, SessionDB)} sessions")


@router.put("/role", tags=["Admin"], response_model=Message,
            dependencies=[permission("assign_roles")])
async def assign_role(db: DBDep, role: str, user: UUID | EmailStr):
    if not (user_db := await get_user_db(db, user, roles=True)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if role in [x.name for x in user_db.roles]:
        raise HTTPException(status.HTTP_208_ALREADY_REPORTED, "Role is set before")

    if not (role_db := await get_role_db(db, role)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")

    user_db.roles.append(role_db)  # noqa sqlalchemy Mapped linter bug
    await db.flush()

    return Message(message=f"Role {role} successfully assigned to user {user}")


@router.get("/roles", tags=["Admin"], response_model=list[dict[str, str | list[dict[str, str]]]],
            dependencies=[permission("get_roles")])
async def get_roles(db: DBDep):
    def fmt(schema: type[OrmSchema], model: TableBase) -> str:
        return schema.model_validate(model).model_dump()

    roles = await get_roles_db(db, permissions=True)
    return [{'type': Role.__name__, **fmt(Role, role), 'permissions':
             [{'type': Permission.__name__, **fmt(Permission, p)} for p in role.permissions]}
            for role in roles]
