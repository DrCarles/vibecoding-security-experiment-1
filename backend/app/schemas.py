import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

from .media import media_url
from .models import Post, User

RESERVED_USERNAMES = {"me", "admin", "api", "settings", "login", "register"}

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Username = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_]{3,30}$")]
NewPassword = Annotated[str, Field(min_length=8, max_length=128)]
AnyPassword = Annotated[str, Field(min_length=1, max_length=128)]


def _check_password_strength(v: str) -> str:
    if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        raise ValueError("Password must contain at least one letter and one number")
    return v


class RegisterIn(BaseModel):
    email: EmailStr
    username: Username
    password: NewPassword
    first_name: Name
    last_name: Name
    age: int = Field(ge=13, le=130)
    address: Address

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("username")
    @classmethod
    def lower_username(cls, v: str) -> str:
        v = v.lower()
        if v in RESERVED_USERNAMES:
            raise ValueError("This username is reserved")
        return v

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return _check_password_strength(v)


class LoginIn(BaseModel):
    login: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
    password: AnyPassword


class ProfileUpdateIn(BaseModel):
    display_name: DisplayName


class PasswordChangeIn(BaseModel):
    current_password: AnyPassword
    new_password: NewPassword

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return _check_password_strength(v)


class UserPublic(BaseModel):
    id: int
    username: str
    display_name: str
    avatar_url: str | None
    created_at: datetime

    @classmethod
    def of(cls, u: User) -> "UserPublic":
        return cls(
            id=u.id,
            username=u.username,
            display_name=u.display_name,
            avatar_url=media_url(u.avatar_path),
            created_at=u.created_at,
        )


class UserMe(UserPublic):
    """The signed-in user's own profile, including private registration details."""

    email: str
    first_name: str
    last_name: str
    age: int
    address: str

    @classmethod
    def of(cls, u: User) -> "UserMe":
        return cls(
            **UserPublic.of(u).model_dump(),
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            age=u.age,
            address=u.address,
        )


class PostOut(BaseModel):
    id: int
    body: str
    image_url: str | None
    created_at: datetime
    author: UserPublic

    @classmethod
    def of(cls, p: Post) -> "PostOut":
        return cls(
            id=p.id,
            body=p.body,
            image_url=media_url(p.image_path),
            created_at=p.created_at,
            author=UserPublic.of(p.author),
        )


class PostPage(BaseModel):
    items: list[PostOut]
    next_cursor: int | None
