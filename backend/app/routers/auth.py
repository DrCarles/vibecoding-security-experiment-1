from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..deps import DbSession
from ..models import User
from ..ratelimit import limiter
from ..schemas import LoginIn, RegisterIn, UserMe
from ..security import clear_session_cookie, hash_password, set_session_cookie, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserMe, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
def register(request: Request, response: Response, data: RegisterIn, db: DbSession) -> UserMe:
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    if db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This username is already taken")

    user = User(
        email=data.email,
        username=data.username,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        age=data.age,
        address=data.address,
        display_name=f"{data.first_name} {data.last_name}"[:50].strip(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent registration.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email or username already taken") from None
    db.refresh(user)
    set_session_cookie(response, user.id, user.token_version)
    return UserMe.of(user)


@router.post("/login", response_model=UserMe)
@limiter.limit("10/minute")
def login(request: Request, response: Response, data: LoginIn, db: DbSession) -> UserMe:
    ident = data.login.lower()
    column = User.email if "@" in ident else User.username
    user = db.scalar(select(User).where(column == ident))
    if not verify_password(data.password, user.password_hash if user else None) or user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username/email or password")
    set_session_cookie(response, user.id, user.token_version)
    return UserMe.of(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    clear_session_cookie(response)
