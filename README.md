## User Authorization and Authentication Backend

### Main information
- DB in `database.py` connected as Middleware (stored in request.scope["db"] in closed state, opens at manual get_db() call, or DBDep dependency in route, closes if was opened at filling response in middleware)
- User and Session handling in `sessions.py` is also connected as Middleware (stored in request.user and request.session from cache or db)
- Secure cookies used for authorization and authentication (stored session UUID, cannot be captured by JS)
- Role-based access control (RBAC) for access to most secure routes based on permissions in roles that user have
- DB field is_superuser in UserDB class for all resources access (including those that cannot be accessed by any RBAC role)
- Using Ruff linter and formatter as pre-commit hook
- Docker Compose available

### Getting uv
Details: https://docs.astral.sh/uv/getting-started/installation/

### Installing

```sh
uv sync
```

### Run example

#### Minimal .env file:
```env
POSTGRES_PASSWORD=root_user_password
POSTGRES_APP_PASSWORD=app_user_password
```
#### Optimal .env file for tests:
```env
POSTGRES_PASSWORD=root_user_password
POSTGRES_APP_PASSWORD=app_user_password
SECURE_COOKIE=False
DROP_DB_AT_START=True
ADD_TEST_DATA=True
```
Notes
- POSTGRES_PASSWORD: used for creating database, creating its owner, and to start docker postgres image
- POSTGRES_APP_PASSWORD: used for database access from app
- SECURE_COOKIE: must be disabled due to http connection, and must be removed when https configured
- DROP_DB_AT_START: recreates all tables
- ADD_TEST_DATA: fill db with test users, roles and permissions (users/passwords in database.py (at lines 36-48))


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

### Alternative run in docker container (build once and run)
```sh
docker compose build
docker compose up
```


### Note
- This is a simple project, completed in 7 days (first commit) - tests is not full, and must be expanded
- Tests covers all main functionality
- Used dict cache must be changed to Redis
- Code coverage report is available after running test
- There is existed, but not used user-agent in session due to time limit (working example available in a neighboring project [Skazo4nik](https://github.com/C0oo1D/Skazo4nik) on GitHub)
