from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import EmailStr

from crud import get_count_db, get_role_db, get_roles_db, get_user_db
from database import DBDep
from models import SessionDB, TableBase, UserDB
from permissions import permission
from schemas import Message, OrmSchema, Permission, Role

router = APIRouter(prefix="/secure")


@router.get("/admin", tags=["Admin"], response_model=Message, dependencies=[permission()])
async def admin(db: DBDep):
    return Message(
        message=f"You are admin! "
        f"DB has {await get_count_db(db, UserDB)} users, "
        f"and {await get_count_db(db, SessionDB)} sessions"
    )


@router.put(
    "/role", tags=["Admin"], response_model=Message, dependencies=[permission("assign_roles")]
)
async def assign_role(db: DBDep, role: str, user: UUID | EmailStr):
    # noinspection PyTypeChecker
    if not (
        user_db := await get_user_db(db, user, with_roles=True)
    ):  # pycharm linter false-positive
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if role in [x.name for x in user_db.roles]:
        raise HTTPException(status.HTTP_208_ALREADY_REPORTED, "Role is set before")

    if not (role_db := await get_role_db(db, role)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")

    user_db.roles.append(role_db)
    await db.flush()

    return Message(message=f"Role {role} successfully assigned to user {user}")


@router.get(
    "/roles",
    tags=["Admin"],
    response_model=list[dict[str, str | list[dict[str, str]]]],
    dependencies=[permission("get_roles")],
)
async def get_roles(db: DBDep):
    def fmt(schema: type[OrmSchema], model: TableBase, **kwargs) -> dict[str, str]:
        return {"type": schema.__name__, **schema.model_validate(model).model_dump(), **kwargs}

    roles = await get_roles_db(db, with_permissions=True)
    return [fmt(Role, r, permissions=[fmt(Permission, p) for p in r.permissions]) for r in roles]
