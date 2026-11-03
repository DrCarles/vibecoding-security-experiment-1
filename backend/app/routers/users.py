from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import select

from ..deps import CurrentUser, DbSession
from ..media import delete_media, save_image
from ..models import User
from ..ratelimit import limiter
from ..schemas import PasswordChangeIn, ProfileUpdateIn, UserMe, UserPublic
from ..security import hash_password, set_session_cookie, verify_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserMe)
def get_me(user: CurrentUser) -> UserMe:
    return UserMe.of(user)


@router.patch("/me", response_model=UserMe)
def update_me(data: ProfileUpdateIn, user: CurrentUser, db: DbSession) -> UserMe:
    user.display_name = data.display_name
    db.commit()
    return UserMe.of(user)


@router.put("/me/avatar", response_model=UserMe)
@limiter.limit("20/hour")
def upload_avatar(request: Request, user: CurrentUser, db: DbSession, file: UploadFile = File(...)) -> UserMe:
    new_path = save_image(file, "avatars")
    old_path = user.avatar_path
    user.avatar_path = new_path
    try:
        db.commit()
    except Exception:
        delete_media(new_path)
        raise
    delete_media(old_path)
    return UserMe.of(user)


@router.delete("/me/avatar", response_model=UserMe)
def remove_avatar(user: CurrentUser, db: DbSession) -> UserMe:
    old_path = user.avatar_path
    user.avatar_path = None
    db.commit()
    delete_media(old_path)
    return UserMe.of(user)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/hour")
def change_password(
    request: Request, response: Response, data: PasswordChangeIn, user: CurrentUser, db: DbSession
) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if data.current_password == data.new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must differ from the current one")
    user.password_hash = hash_password(data.new_password)
    # Signs out every other session; this one gets a fresh cookie below.
    user.token_version += 1
    db.commit()
    set_session_cookie(response, user.id, user.token_version)


@router.get("/{username}", response_model=UserPublic)
def get_user(username: str, db: DbSession) -> UserPublic:
    user = db.scalar(select(User).where(User.username == username.lower()))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return UserPublic.of(user)
