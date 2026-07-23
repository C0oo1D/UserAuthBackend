from models import PermissionDB, RoleDB, UserDB
from settings import settings

hasher = settings.password_hasher.hash


def get_example_data():
    permission_get_roles = PermissionDB(
        name="Get roles",
        codename="get_roles",
        description="Allows get roles list with permissions",
    )
    permission_assign_roles = PermissionDB(
        name="Assign roles", codename="assign_roles", description="Allows assign roles for users"
    )

    role_admin = RoleDB(
        name="Administrator", description="Have all permissions, cannot access superuser endpoints"
    )
    role_admin.permissions.extend((permission_get_roles, permission_assign_roles))

    role_moderator = RoleDB(name="Moderator", description="Can see permissions")
    role_moderator.permissions.append(permission_get_roles)

    user_superuser = UserDB(
        email="admin@example.com",
        firstname="Admin",
        is_superuser=True,
        hashed_password=hasher("su_password"),
    )

    user_admin = UserDB(
        email="i_am_admin@example.com",
        firstname="i am admin",
        lastname="or not",
        hashed_password=hasher("adm_password"),
    )
    user_admin.roles.extend((role_moderator, role_admin))

    user_moderator = UserDB(
        email="moder@example.com",
        firstname="moder",
        surname="what a sur",
        hashed_password=hasher("mod_password"),
    )
    user_moderator.roles.append(role_moderator)

    user_standard = UserDB(
        email="stduser@example.com", firstname="filippo", hashed_password=hasher("std_password")
    )

    return (
        permission_get_roles,
        permission_assign_roles,
        role_admin,
        role_moderator,
        user_superuser,
        user_admin,
        user_moderator,
        user_standard,
    )
