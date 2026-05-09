from ast import literal_eval
from datetime import datetime, UTC, timedelta
from functools import partial

from argon2 import PasswordHasher
from dotenv.main import DotEnv


get_utc_now = partial(datetime.now, tz=UTC)  # sqlalchemy.func.utcnow() fails in asyncpg
_env = DotEnv('.env')


def _parse(key: str, default=None):
    return literal_eval(value) if (value := _env.get(key)) else default


def _parse_kw(key: str, default: dict | None = None) -> dict:
    return dict(value) if (value := _parse(key)) else default or {}


db_url = _env.get('db_url')
db_echo = _parse('db_echo', False)
password_hasher = PasswordHasher(**_parse_kw('password_hasher_kw'))
session_expire = timedelta(**_parse_kw('session_expire_kw', default={'days': 14}))
session_cache_expire = timedelta(**_parse_kw('session_cache_expire_kw', default={'hours': 6}))
secure_cookie = _parse('secure_cookie', True)
debug = _parse('debug', False)
drop_db_at_start = _parse('drop_db_at_start', False)
add_test_data = _parse('add_test_data', False)
