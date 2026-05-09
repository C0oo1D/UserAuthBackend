from fastapi import APIRouter, Request, Response, HTTPException, status
from pydantic import EmailStr, SecretStr

from crud import (get_user_db, create_user_db, create_session_db, update_user_db, suspend_user_db,
                  delete_sessions_db, authenticate_user_db, delete_session_db)
from database import DBDep
from schemas import Message, RegisterUserForm, UpdateUserForm, UserInfo, User
from routers import fmt_errors
from sessions import UserDep, SessionDep, set_cookie, del_cookie, cache


router = APIRouter(prefix='/user')


@router.post("/register", tags=['User'], response_model=Message, responses=fmt_errors(409))
async def register(request: Request, response: Response, db: DBDep, form: RegisterUserForm):
    """Register user"""
    if request.user:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot register user when login completed")

    if await get_user_db(db, str(form.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = await create_user_db(db, form)
    session = await create_session_db(db, user.id, request.headers.get("user-agent"))
    set_cookie(response, str(session.id))
    return Message(message="User registration successful")


@router.patch("/update", tags=['User'], response_model=Message)
async def update(db: DBDep, user: UserDep, form: UpdateUserForm):
    """Update user"""
    if not (user_db := await authenticate_user_db(db, user.email,
                                                  form.password.get_secret_value())):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong password")

    exists = user.model_dump()
    new = form.model_dump()
    if not new.get('hashed_password'):
        new.pop('hashed_password', None)
    if not (changes := {k: v for k, v in new.items() if exists[k] != v}):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "There is nothing to change")

    if (email := changes.get('email')) and await get_user_db(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    await update_user_db(db, user.id, **changes)
    cache.update_user(User.model_validate(user_db))
    return Message(message="User update successful")


@router.delete("/suspend", tags=['User'], response_model=Message, responses=fmt_errors(401))
async def suspend(password: SecretStr, response: Response, db: DBDep, user: UserDep):
    """Suspend user"""
    if not (user_db := await authenticate_user_db(db, user.email, password.get_secret_value())):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong password")

    await suspend_user_db(db, user_db)
    await delete_sessions_db(db, user.id)

    del_cookie(response)
    cache.delete_user(user)
    return Message(message="User suspend successful")


@router.post("/login", tags=['Auth'], response_model=Message, responses=fmt_errors(403, 409))
async def login(email: EmailStr, password: SecretStr, request: Request, response: Response,
                     db: DBDep):
    """Login user"""
    if not (user_db := await authenticate_user_db(db, str(email), password.get_secret_value())):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong email or password")
    if not user_db.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is suspended")

    session = await create_session_db(db, user_db.id, request.headers.get("user-agent"))  # noqa sqlalchemy Mapped linter bug
    set_cookie(response, str(session.id))
    return Message(message="User login successful")


@router.post("/logout", tags=['Auth'], response_model=Message, responses=fmt_errors(409))
async def logout(response: Response, db: DBDep, session: SessionDep):
    """Logout user"""
    await delete_session_db(db, session.id)
    del_cookie(response)
    cache.delete_session(session)
    return Message(message="User logout successful")


@router.get("", tags=['Profile'], response_model=UserInfo, responses=fmt_errors(401))
async def show(user: UserDep):
    """Show current user profile"""
    return user.get_info()


