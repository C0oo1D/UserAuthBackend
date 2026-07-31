## User Authorization and Authentication Backend

### Main information
- DB in `database.py` connected as Middleware and lifetime (used SQLAlchemy with async PostgreSQL driver, stored in `request.scope["db"]` in closed state, opens at manual `get_db()` call, or `DBDep` dependency in route, closes if was opened at filling response in middleware)
- Cache in `cache.py` connected as lifetime (used async Redis, stored in `request.app.state["cache"]`, access through `get_cache()` call, or `CacheDep` dependency in route)
- Session/User in `sessions.py` connected as Middleware and lifetime (stored in `request.session`/`request.user`(`request.session.user`), access through `get_session()`/`get_user()` call, or `SessionDep`/`UserDep` dependency in route, both filled from cache or db)
- Secure cookies used for authorization and authentication - stored session UUID, cannot be captured by JS
- Role-based access control (RBAC) for access to the most of secure routes based on permissions in roles that user have
- DB field `is_superuser` in `UserDB` class for all resources access (including those that cannot be accessed by any RBAC role)
- Pydantic-settings nested structures used for settings
- Using Ruff linter and formatter as pre-commit hook
- Docker Compose file available for start without installing PostgreSQL and Redis
- Loguru is used for logging to decrease boilerplate code, it is also configurable through env


### Getting uv
Details: https://docs.astral.sh/uv/getting-started/installation/

### Installing

```sh
uv sync
```

### Required .env file example

#### Minimal:
```env
POSTGRES_ROOT_PASSWORD=root_user_password
POSTGRES_PASSWORD=app_user_password
```
#### Optimal for tests:
```env
POSTGRES_ROOT_PASSWORD=root_user_password
POSTGRES_PASSWORD=app_user_password
SECURE_COOKIE=False
DROP_DB_AT_START=True
ADD_EXAMPLE_DATA=True
```
Notes
- POSTGRES_ROOT_PASSWORD: used for creating database, creating its owner, and to start docker postgres image
- POSTGRES_PASSWORD: used for database access from app
- SECURE_COOKIE: must be disabled due to http connection, and must be removed when https configured
- DROP_DB_AT_START: recreates all tables
- ADD_EXAMPLE_DATA: fill db with example users, roles and permissions (users/passwords in example_data.py)


#### Run:
```sh
uv run src/auth/main.py
```
Endpoints OpenAPI docs available at http://127.0.0.1/docs during run, host/port is configurable

### Testing
```sh
uv run pytest
```

### Checking linter rules and formatting files
```sh
uv run ruff check
uv run ruff format
```

### Run in docker container commands: build (use once), start as daemon, shut down
```sh
docker compose build
docker compose up -d
docker compose down
```


### Note
- This is a simple project, completed in 7 days (first commit) - tests is not full, and must be expanded
- Tests covers all main functionality
- Code coverage report is available after running test
- There is existed, but not used user-agent in session due to time limit (working example available in a neighboring project [Skazo4nik](https://github.com/C0oo1D/Skazo4nik) on GitHub)
- Added multi-host for PostgreSQL, but tested without configured replication