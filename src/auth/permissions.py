from fastapi import HTTPException, status
from fastapi.params import Depends

from crud import get_user_db
from database import DBDep
from models import UserDB
from sessions import UserDep


def _has_permission(user: UserDB, codename: str) -> bool:
    if not codename:
        return False
    for role in user.roles:
        for perm in role.permissions:
            if perm.codename == codename:
                return True
    return False


def permission(codename: str = "") -> Depends:
    async def check_permissions(db: DBDep, user: UserDep):
        if user.is_superuser:
            return
        if not (user_db := await get_user_db(db, user.id, with_roles=True, with_permissions=True)):
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Cannot find {user.id}")
        if _has_permission(user_db, codename):
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")

    return Depends(check_permissions)
