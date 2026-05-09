from checks import sort_recursively


class User:
    names = {"firstname": None, "lastname": None, "surname": None}

    def __init__(self, reg_data: dict, upd_data: dict):
        self.reg_data = reg_data
        self.reg = {'json': self.reg_data}
        self.show = self.title(self.names | self.remove_passwords(self.reg_data))

        self.upd_data = self.show | upd_data
        self.upd = {"json": self.upd_data}
        self.show_upd = self.title(self.names | self.remove_passwords(self.upd_data))

        last_password = self.upd_data.get('new_password') or self.reg_data['password']
        self.sus = {'params': {'password': last_password}}

    @staticmethod
    def remove_passwords(data: dict) -> dict:
        return {k: v for k, v in data.items() if k not in ('password', 'confirm_password',
                                                           'new_password', 'confirm_new_password')}

    def title(self, data: dict) -> dict:
        return {k: v.title() if k in self.names and v else v for k, v in data.items()}

    @staticmethod
    def _get(field: str, data: dict | str):
        if isinstance(data, dict):
            data = data['json'].get(field)
        return data

    def _login(self, email: dict | str, password: dict | str, default: dict):
        email = self._get('email', email or default)
        password = (self._get('new_password', password or default) or
                    self._get('password', password or default))
        return {'params': {'email': email, 'password': password}}

    def login(self, email: dict | str = '', password: dict | str = ''):
        return self._login(email, password, self.reg)

    def login_upd(self, email: dict | str = '', password: dict | str = ''):
        return self._login(email, password, self.upd)

    @property
    def upd_from_reg(self):
        return {'json': {k: v for k, v in self.reg_data.items() if k != 'confirm_password'}}


user1 = User({'firstname': 'user1', 'email': 'user1@test.com',
              'password': '12345678', 'confirm_password': '12345678'},
             {'password': '12345678', 'surname': 'ken',
              'new_password': '123456789', 'confirm_new_password': '123456789'})
user2 = User({'firstname': 'user2', 'email': 'user2@test.com', 'lastname': 'meow',
              'password': '12345679', 'confirm_password': '12345679'},
             {'password': '12345679', 'lastname': 'more than'})
user3 = User({'firstname': 'user3', 'email': 'user3@test.com', 'lastname': 'meo', 'surname': 'wan',
              'password': '1234567890', 'confirm_password': '1234567890'},
             {'password': '1234567890', 'email': 'user3upd@test.com', 'surname': None})


class Fixed:
    reg = {'message': 'User registration successful'}
    reg_403 = {'detail': 'Cannot register user when login completed'}
    reg_409 = {'detail': 'Email already registered'}
    update = {'message': 'User update successful'}
    update_400 = {'detail': 'There is nothing to change'}
    update_403 = {'detail': 'Wrong password'}
    update_409 = {'detail': 'Email already registered'}
    suspend = {'message': 'User suspend successful'}
    suspend_403 = {'detail': 'Wrong password'}
    login = {'message': 'User login successful'}
    login_403 = {'detail': 'Wrong email or password'}
    login_409 = {'detail': 'User is suspended'}
    logout = {'message': 'User logout successful'}
    common_401 = {'detail': 'Unauthorized'}
    perm_403 = {'detail': 'Permission denied'}
    assign = {'message': 'Role Moderator successfully assigned to user stduser@example.com'}
    assign_208 = {'detail': 'Role is set before'}
    assign_404_user = {'detail': 'User not found'}
    assign_404_role = {'detail': 'Role not found'}
    roles = sort_recursively([
        {'type': 'Role',
         'name': 'Administrator',
         'description': 'Have all permissions, cannot access superuser endpoints',
         'permissions': [
             {'type': 'Permission',
              'name': 'Get roles',
              'codename': 'get_roles',
              'description': 'Allows get roles list with permissions'
              },
             {'type': 'Permission',
              'name': 'Assign roles',
              'codename': 'assign_roles',
              'description': 'Allows assign roles for users'
              }
         ]},
        {'type': 'Role',
         'name': 'Moderator',
         'description': 'Can see permissions',
         'permissions': [
             {'type': 'Permission',
              'name': 'Get roles',
              'codename': 'get_roles',
              'description': 'Allows get roles list with permissions'
              }
         ]}
    ])
