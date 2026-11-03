from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("age BETWEEN 13 AND 130", name="ck_users_age"),
        Index("ux_users_email", "email", unique=True),
        Index("ux_users_username", "username", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    username: Mapped[str] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int] = mapped_column(SmallInteger)
    address: Mapped[str] = mapped_column(String(500))
    display_name: Mapped[str] = mapped_column(String(50))
    avatar_path: Mapped[str | None] = mapped_column(String(255))
    # Bumped on password change so every previously issued session stops working.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint("char_length(body) > 0 OR image_path IS NOT NULL", name="ck_posts_not_empty"),
        Index("ix_posts_author_id_id", "author_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(String(280), default="", server_default="")
    image_path: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    author: Mapped[User] = relationship()
