from collections.abc import Callable
from functools import partial
from threading import Thread
from time import sleep

import pytest
from httpx import Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from checks import equal_resp, msg_422, sort_recursively
from data import Auth, user1, user2, user3
from example_data import get_example_data
from models import TableBase
from server import LoggedServer, run
from settings import settings

db_engine = create_engine(settings.postgres.test_url)
_base_url = f"http://{settings.server.host}:{settings.server.port}"


@pytest.fixture(scope="module")
def server():
    """TestClient is not working due to event loop closed conflicts between httpx and asyncpg"""
    server = LoggedServer(config := settings.server.config_tests)
    server_thread = Thread(target=partial(run, config, server), daemon=True)
    server_thread.start()

    retries = 0
    while not server.started and retries < 100:
        sleep(0.1)
        retries += 1
    if retries >= 100:
        raise SystemError(f"Server is not started after {retries // 10}s")

    yield

    server.should_exit = True
    server_thread.join(timeout=5)


@pytest.fixture(scope="class")
def db_recreate(server):
    TableBase.metadata.drop_all(db_engine)
    TableBase.metadata.create_all(db_engine)
    with sessionmaker(db_engine).begin() as session:
        session.add_all(get_example_data())

    return server


@pytest.fixture(scope="class")
def client(db_recreate):  # noqa: ARG001 fixture-related argument
    return Client(base_url=_base_url)


# Fixed result funcs
login_ok = equal_resp(200, Auth.login, set_cookie=True)
logout_ok = equal_resp(200, Auth.logout, set_cookie=True)
auth_needed = equal_resp(401, Auth.common_401, set_cookie=False)
perm_denied = equal_resp(403, Auth.perm_403, set_cookie=False)
perm_roles = equal_resp(200, Auth.roles, set_cookie=False, json_handler=sort_recursively)
perm_assign = equal_resp(200, Auth.assign, set_cookie=False, json_handler=sort_recursively)
perm_assign_422 = equal_resp(422, set_cookie=False)
perm_assign_208 = equal_resp(208, Auth.assign_208, set_cookie=False)
perm_assign_404_role = equal_resp(404, Auth.assign_404_role, set_cookie=False)
perm_assign_404_user = equal_resp(404, Auth.assign_404_user, set_cookie=False)

# User
register = ("POST", "/user/register")
update = ("PATCH", "/user/update")
suspend = ("DELETE", "/user/suspend")
login = ("POST", "/user/login")
logout = ("POST", "/user/logout")
show = ("GET", "/user")

# Secure
admin = ("GET", "/secure/admin")
assign = ("PUT", "/secure/role")
roles = ("GET", "/secure/roles")

# Other data
u1reg_pass = user1.reg_data["password"]
u1upd_pass = user1.upd_data["password"]
u2reg_pass = user2.reg_data["password"]

update_email_exists = {"json": {"password": u1reg_pass, "email": user2.reg_data["email"]}}
update_passwords_equal = {"json": {"password": u1reg_pass, "new_password": u1reg_pass}}
update_passwords_partial = {"json": {"password": u1reg_pass, "confirm_new_password": u1reg_pass}}
update_passwords_mismatch = {
    "json": {
        "password": u1reg_pass,
        "new_password": u1upd_pass,
        "confirm_new_password": u2reg_pass,
    }
}

su_cred = {"params": {"email": "admin@example.com", "password": "su_password"}}
adm_cred = {"params": {"email": "i_am_admin@example.com", "password": "adm_password"}}
mod_cred = {"params": {"email": "moder@example.com", "password": "mod_password"}}
std_cred = {"params": {"email": "stduser@example.com", "password": "std_password"}}

assign_mod = {"params": {"role": "Moderator", "user": "stduser@example.com"}}
assign_ne_role = {"params": {"role": "Not Exists", "user": "stduser@example.com"}}
assign_ne_user = {"params": {"role": "Moderator", "user": "not_exists@example.com"}}
su_str = {"message": "You are admin! DB has 4 users, and 1 sessions"}


user_params = [
    # Register, show and logout user tests
    pytest.param(auth_needed, show, {}, id="Show when not login"),
    pytest.param(
        equal_resp(200, Auth.reg, set_cookie=True), register, user1.reg, id="Register user1"
    ),
    pytest.param(equal_resp(200, user1.show, set_cookie=False), show, {}, id="Show user1"),
    pytest.param(
        equal_resp(403, Auth.reg_403, set_cookie=False),
        register,
        user1.reg,
        id="Register exists when login",
    ),
    pytest.param(
        equal_resp(403, Auth.reg_403, set_cookie=False),
        register,
        user2.reg,
        id="Register not exists when login",
    ),
    pytest.param(logout_ok, logout, {}, id="Logout reg user1"),
    pytest.param(
        equal_resp(409, Auth.reg_409, set_cookie=False),
        register,
        user1.reg,
        id="Register email exists",
    ),
    pytest.param(
        equal_resp(200, Auth.reg, set_cookie=True), register, user2.reg, id="Register user2"
    ),
    pytest.param(equal_resp(200, user2.show, set_cookie=False), show, {}, id="Show user2"),
    pytest.param(logout_ok, logout, {}, id="Logout reg user2"),
    pytest.param(
        equal_resp(200, Auth.reg, set_cookie=True), register, user3.reg, id="Register user3"
    ),
    pytest.param(equal_resp(200, user3.show, set_cookie=False), show, {}, id="Show user3"),
    pytest.param(logout_ok, logout, {}, id="Logout reg user3"),
    # Update and login user tests
    pytest.param(auth_needed, update, user1.upd, id="Update when not login"),
    pytest.param(
        equal_resp(403, Auth.login_403, set_cookie=False),
        login,
        user1.login(email=user2.reg),
        id="Login wrong email",
    ),
    pytest.param(
        equal_resp(403, Auth.login_403, set_cookie=False),
        login,
        user1.login(password=user2.reg),
        id="Login wrong password",
    ),
    pytest.param(login_ok, login, user1.login(), id="Login upd user1"),
    pytest.param(
        equal_resp(400, Auth.update_400, set_cookie=False),
        update,
        user1.upd_from_reg,
        id="Update no new data",
    ),
    pytest.param(
        equal_resp(403, Auth.update_403, set_cookie=False),
        update,
        user2.upd_from_reg,
        id="Update wrong password",
    ),
    pytest.param(
        equal_resp(409, Auth.update_409, set_cookie=False),
        update,
        update_email_exists,
        id="Update email exists",
    ),
    pytest.param(
        equal_resp(422, Auth.update_422_equal, set_cookie=False, json_handler=msg_422),
        update,
        update_passwords_equal,
        id="Update passwords equal",
    ),
    pytest.param(
        equal_resp(422, Auth.update_422_partial, set_cookie=False, json_handler=msg_422),
        update,
        update_passwords_partial,
        id="Update passwords partial",
    ),
    pytest.param(
        equal_resp(422, Auth.update_422_mismatch, set_cookie=False, json_handler=msg_422),
        update,
        update_passwords_mismatch,
        id="Update passwords mismatch",
    ),
    pytest.param(
        equal_resp(200, Auth.update, set_cookie=False), update, user1.upd, id="Update user1"
    ),
    pytest.param(
        equal_resp(200, user1.show_upd, set_cookie=False), show, {}, id="Show updated user1"
    ),
    pytest.param(logout_ok, logout, {}, id="Logout upd user1"),
    pytest.param(login_ok, login, user2.login(), id="Login upd user2"),
    pytest.param(
        equal_resp(200, Auth.update, set_cookie=False), update, user2.upd, id="Update user2"
    ),
    pytest.param(
        equal_resp(200, user2.show_upd, set_cookie=False), show, {}, id="Show updated user2"
    ),
    pytest.param(logout_ok, logout, {}, id="Logout upd user2"),
    pytest.param(login_ok, login, user3.login(), id="Login upd user3"),
    pytest.param(
        equal_resp(200, Auth.update, set_cookie=False), update, user3.upd, id="Update user3"
    ),
    pytest.param(
        equal_resp(200, user3.show_upd, set_cookie=False), show, {}, id="Show updated user3"
    ),
    pytest.param(logout_ok, logout, {}, id="Logout upd user3"),
    # Suspend user tests
    pytest.param(auth_needed, suspend, user1.sus, id="Suspend when not login"),
    pytest.param(login_ok, login, user1.login_upd(), id="Login sus user1"),
    pytest.param(
        equal_resp(403, Auth.suspend_403, set_cookie=False),
        suspend,
        user2.sus,
        id="Suspend wrong password",
    ),
    pytest.param(
        equal_resp(200, Auth.suspend, set_cookie=True), suspend, user1.sus, id="Suspend user1"
    ),
    pytest.param(
        equal_resp(409, Auth.reg_409, set_cookie=False),
        register,
        user1.reg,
        id="Register email exists after suspend",
    ),
    pytest.param(
        equal_resp(403, Auth.login_403, set_cookie=False),
        login,
        user1.login(),
        id="Login after suspend old password",
    ),
    pytest.param(
        equal_resp(409, Auth.login_409, set_cookie=False),
        login,
        user1.login_upd(),
        id="Login after suspend",
    ),
    # todo: Multiple sessions per user tests
]

secure_params = [
    # Access when not login
    pytest.param(auth_needed, roles, {}, id="Access roles when not login"),
    pytest.param(auth_needed, assign, {}, id="Access assign when not login"),
    pytest.param(auth_needed, admin, {}, id="Access admin when not login"),
    # User tests
    pytest.param(login_ok, login, std_cred, id="Login User"),
    pytest.param(perm_denied, roles, {}, id="Access roles as User"),
    pytest.param(perm_denied, assign, {}, id="Access assign as User without params"),
    pytest.param(perm_denied, assign, assign_mod, id="Access assign as User"),
    pytest.param(perm_denied, admin, {}, id="Access admin as User"),
    pytest.param(logout_ok, logout, {}, id="Logout User"),
    # Moderator tests
    pytest.param(login_ok, login, mod_cred, id="Login Moderator"),
    pytest.param(perm_roles, roles, {}, id="Access roles as Moderator"),
    pytest.param(perm_denied, assign, {}, id="Access assign as Moderator without params"),
    pytest.param(perm_denied, assign, assign_mod, id="Access assign as Moderator"),
    pytest.param(perm_denied, admin, {}, id="Access admin as Moderator"),
    pytest.param(logout_ok, logout, {}, id="Logout Moderator"),
    # Administrator tests
    pytest.param(login_ok, login, adm_cred, id="Login Administrator"),
    pytest.param(perm_roles, roles, {}, id="Access roles as Administrator"),
    pytest.param(perm_assign_422, assign, {}, id="Access assign as Administrator without params"),
    pytest.param(perm_assign, assign, assign_mod, id="Access assign as Administrator"),
    pytest.param(perm_denied, admin, {}, id="Access admin as Administrator"),
    pytest.param(logout_ok, logout, {}, id="Logout Administrator"),
    # UserModerator tests
    pytest.param(login_ok, login, std_cred, id="Login UserModerator"),
    pytest.param(perm_roles, roles, {}, id="Access roles as UserModerator"),
    pytest.param(perm_denied, assign, {}, id="Access assign as UserModerator without params"),
    pytest.param(perm_denied, assign, assign_mod, id="Access assign as UserModerator"),
    pytest.param(perm_denied, admin, {}, id="Access admin as UserModerator"),
    pytest.param(logout_ok, logout, {}, id="Logout UserModerator"),
    # Superuser tests
    pytest.param(login_ok, login, su_cred, id="Login superuser"),
    pytest.param(perm_roles, roles, {}, id="Access roles as superuser"),
    pytest.param(perm_assign_422, assign, {}, id="Access assign as superuser without params"),
    pytest.param(perm_assign_208, assign, assign_mod, id="Access assigned before"),
    pytest.param(perm_assign_404_role, assign, assign_ne_role, id="Access assign not exists role"),
    pytest.param(perm_assign_404_user, assign, assign_ne_user, id="Access assign not exists user"),
    pytest.param(equal_resp(200, su_str), admin, {}, id="Access admin as superuser"),
    pytest.param(logout_ok, logout, {}, id="Logout superuser"),
]


class TestUser:
    @pytest.mark.parametrize(("result_func", "args", "kwargs"), user_params)
    def test_user(self, client: Client, result_func: Callable, args, kwargs):
        result_func(client.request(*args, **kwargs))


class TestSecure:
    @pytest.mark.parametrize(("result_func", "args", "kwargs"), secure_params)
    def test_secure(self, client: Client, result_func: Callable, args, kwargs):
        result_func(client.request(*args, **kwargs))
