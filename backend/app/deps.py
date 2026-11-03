from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User
from .security import decode_session_token

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbSession) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    token = request.cookies.get(get_settings().cookie_name)
    if not token:
        raise unauthorized
    payload = decode_session_token(token)
    if payload is None:
        raise unauthorized
    try:
        user = db.get(User, int(payload["sub"]))
    except (TypeError, ValueError):
        raise unauthorized from None
    if user is None or user.token_version != payload.get("ver"):
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
