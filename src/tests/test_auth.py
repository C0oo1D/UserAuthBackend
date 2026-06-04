from collections.abc import Callable

from httpx import Client
from pytest import mark, param

from checks import is_equal, sort_recursively
from data import Fixed, user1, user2, user3

# Fixed result funcs
login_ok = is_equal(200, Fixed.login, set_cookie=True)
logout_ok = is_equal(200, Fixed.logout, set_cookie=True)
auth_needed = is_equal(401, Fixed.common_401, set_cookie=False)
perm_denied = is_equal(403, Fixed.perm_403, set_cookie=False)
perm_roles = is_equal(200, Fixed.roles, set_cookie=False, json_handler=sort_recursively)
perm_assign = is_equal(200, Fixed.assign, set_cookie=False, json_handler=sort_recursively)
perm_assign_422 = is_equal(422, set_cookie=False)
perm_assign_208 = is_equal(208, Fixed.assign_208, set_cookie=False)
perm_assign_404_role = is_equal(404, Fixed.assign_404_role, set_cookie=False)
perm_assign_404_user = is_equal(404, Fixed.assign_404_user, set_cookie=False)

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
update_email_exists = {'json': {'password': user1.reg_data['password'],
                                'email': user2.reg_data['email']}}

su_cred = {'params': {'email': 'admin@example.com', 'password': 'su_password'}}
adm_cred = {'params': {'email': 'i_am_admin@example.com', 'password': 'adm_password'}}
mod_cred = {'params': {'email': 'moder@example.com', 'password': 'mod_password'}}
std_cred = {'params': {'email': 'stduser@example.com', 'password': 'std_password'}}

assign_mod = {'params': {'role': 'Moderator', 'user': 'stduser@example.com'}}
assign_ne_role = {'params': {'role': 'Not Exists', 'user': 'stduser@example.com'}}
assign_ne_user = {'params': {'role': 'Moderator', 'user': 'not_exists@example.com'}}
su_str = {'message': 'You are admin! DB has 4 users, and 1 sessions'}


class TestUser:
    @mark.parametrize("result_func, args, kwargs", [
        # Register, show and logout user tests
        param(auth_needed, show, {}, id='Show when not login'),
        param(is_equal(200, Fixed.reg, set_cookie=True), register, user1.reg, id='Register user1'),
        param(is_equal(200, user1.show, set_cookie=False), show, {}, id='Show user1'),
        param(is_equal(403, Fixed.reg_403, set_cookie=False), register, user1.reg,
              id='Register exists when login'),
        param(is_equal(403, Fixed.reg_403, set_cookie=False), register, user2.reg,
              id='Register not exists when login'),
        param(logout_ok, logout, {}, id='Logout reg user1'),
        param(is_equal(409, Fixed.reg_409, set_cookie=False), register, user1.reg,
              id='Register email exists'),
        param(is_equal(200, Fixed.reg, set_cookie=True), register, user2.reg, id='Register user2'),
        param(is_equal(200, user2.show, set_cookie=False), show, {}, id='Show user2'),
        param(logout_ok, logout, {}, id='Logout reg user2'),
        param(is_equal(200, Fixed.reg, set_cookie=True), register, user3.reg, id='Register user3'),
        param(is_equal(200, user3.show, set_cookie=False), show, {}, id='Show user3'),
        param(logout_ok, logout, {}, id='Logout reg user3'),

        # Update and login user tests
        param(auth_needed, update, user1.upd, id='Update when not login'),
        param(is_equal(403, Fixed.login_403, set_cookie=False), login,
              user1.login(email=user2.reg), id='Login wrong email'),
        param(is_equal(403, Fixed.login_403, set_cookie=False), login,
              user1.login(password=user2.reg), id='Login wrong password'),
        param(login_ok, login, user1.login(), id='Login upd user1'),
        param(is_equal(400, Fixed.update_400, set_cookie=False), update, user1.upd_from_reg,
              id='Update no new data'),
        param(is_equal(403, Fixed.update_403, set_cookie=False), update, user2.upd_from_reg,
              id='Update wrong password'),
        param(is_equal(409, Fixed.update_409, set_cookie=False), update, update_email_exists,
              id='Update email exists'),
        param(is_equal(200, Fixed.update, set_cookie=False), update, user1.upd, id='Update user1'),
        param(is_equal(200, user1.show_upd, set_cookie=False), show, {}, id='Show updated user1'),
        param(logout_ok, logout, {}, id='Logout upd user1'),
        param(login_ok, login, user2.login(), id='Login upd user2'),
        param(is_equal(200, Fixed.update, set_cookie=False), update, user2.upd, id='Update user2'),
        param(is_equal(200, user2.show_upd, set_cookie=False), show, {}, id='Show updated user2'),
        param(logout_ok, logout, {}, id='Logout upd user2'),
        param(login_ok, login, user3.login(), id='Login upd user3'),
        param(is_equal(200, Fixed.update, set_cookie=False), update, user3.upd, id='Update user3'),
        param(is_equal(200, user3.show_upd, set_cookie=False), show, {}, id='Show updated user3'),
        param(logout_ok, logout, {}, id='Logout upd user3'),

        # Suspend user tests
        param(auth_needed, suspend, user1.sus, id='Suspend when not login'),
        param(login_ok, login, user1.login_upd(), id='Login sus user1'),
        param(is_equal(403, Fixed.suspend_403, set_cookie=False), suspend, user2.sus,
              id='Suspend wrong password'),
        param(is_equal(200, Fixed.suspend, set_cookie=True), suspend, user1.sus,
              id='Suspend user1'),
        param(is_equal(409, Fixed.reg_409, set_cookie=False), register, user1.reg,
              id='Register email exists'),
        param(is_equal(403, Fixed.login_403, set_cookie=False), login, user1.login(),
              id='Login after suspend old password'),
        param(is_equal(409, Fixed.login_409, set_cookie=False), login, user1.login_upd(),
              id='Login after suspend'),

        # todo: Multiple sessions per user tests
        # todo: Pydantic validators tests
    ])
    def test_user(self, client: Client, result_func: Callable, args, kwargs):
        assert result_func(client.request(*args, **kwargs))


class TestSecure:
    @mark.parametrize("result_func, args, kwargs", [
        # Access when not login
        param(auth_needed, roles, {}, id='Access roles when not login'),
        param(auth_needed, assign, {}, id='Access assign when not login'),
        param(auth_needed, admin, {}, id='Access admin when not login'),

        # User tests
        param(login_ok, login, std_cred, id='Login User'),
        param(perm_denied, roles, {}, id='Access roles as User'),
        param(perm_denied, assign, {}, id='Access assign as User without params'),
        param(perm_denied, assign, assign_mod, id='Access assign as User'),
        param(perm_denied, admin, {}, id='Access admin as User'),
        param(logout_ok, logout, {}, id='Logout User'),

        # Moderator tests
        param(login_ok, login, mod_cred, id='Login Moderator'),
        param(perm_roles, roles, {}, id='Access roles as Moderator'),
        param(perm_denied, assign, {}, id='Access assign as Moderator without params'),
        param(perm_denied, assign, assign_mod, id='Access assign as Moderator'),
        param(perm_denied, admin, {}, id='Access admin as Moderator'),
        param(logout_ok, logout, {}, id='Logout Moderator'),

        # Administrator tests
        param(login_ok, login, adm_cred, id='Login Administrator'),
        param(perm_roles, roles, {}, id='Access roles as Administrator'),
        param(perm_assign_422, assign, {}, id='Access assign as Administrator without params'),
        param(perm_assign, assign, assign_mod, id='Access assign as Administrator'),
        param(perm_denied, admin, {}, id='Access admin as Administrator'),
        param(logout_ok, logout, {}, id='Logout Administrator'),

        # UserModerator tests
        param(login_ok, login, std_cred, id='Login UserModerator'),
        param(perm_roles, roles, {}, id='Access roles as UserModerator'),
        param(perm_denied, assign, {}, id='Access assign as UserModerator without params'),
        param(perm_denied, assign, assign_mod, id='Access assign as UserModerator'),
        param(perm_denied, admin, {}, id='Access admin as UserModerator'),
        param(logout_ok, logout, {}, id='Logout UserModerator'),

        # Superuser tests
        param(login_ok, login, su_cred, id='Login superuser'),
        param(perm_roles, roles, {}, id='Access roles as superuser'),
        param(perm_assign_422, assign, {}, id='Access assign as superuser without params'),
        param(perm_assign_208, assign, assign_mod, id='Access assigned before'),
        param(perm_assign_404_role, assign, assign_ne_role, id='Access assign not exists role'),
        param(perm_assign_404_user, assign, assign_ne_user, id='Access assign not exists user'),
        param(is_equal(200, su_str), admin, {}, id='Access admin as superuser'),
        param(logout_ok, logout, {}, id='Logout superuser'),
    ])
    def test_secure(self, client: Client, result_func: Callable, args, kwargs):
        assert result_func(client.request(*args, **kwargs))
