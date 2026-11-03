from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..deps import CurrentUser, DbSession
from ..media import delete_media, save_image
from ..models import Post, User
from ..ratelimit import limiter
from ..schemas import PostOut, PostPage

router = APIRouter(prefix="/api/posts", tags=["posts"])

MAX_POST_LENGTH = 280


@router.get("", response_model=PostPage)
def list_posts(
    db: DbSession,
    before: Annotated[int | None, Query(gt=0, description="Return posts older than this post id")] = None,
    author: Annotated[str | None, Query(max_length=30)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> PostPage:
    stmt = select(Post).options(joinedload(Post.author)).order_by(Post.id.desc()).limit(limit + 1)
    if before is not None:
        stmt = stmt.where(Post.id < before)
    if author:
        author_id = db.scalar(select(User.id).where(User.username == author.lower()))
        if author_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        stmt = stmt.where(Post.author_id == author_id)

    rows = list(db.scalars(stmt))
    has_more = len(rows) > limit
    rows = rows[:limit]
    return PostPage(items=[PostOut.of(p) for p in rows], next_cursor=rows[-1].id if has_more else None)


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def create_post(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    body: Annotated[str, Form()] = "",
    image: Annotated[UploadFile | None, File()] = None,
) -> PostOut:
    body = body.strip()
    if len(body) > MAX_POST_LENGTH:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Posts are limited to {MAX_POST_LENGTH} characters")
    has_image = image is not None and bool(image.filename)
    if not body and not has_image:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Write something or attach an image")

    image_path = save_image(image, "posts") if has_image else None
    post = Post(author_id=user.id, body=body, image_path=image_path)
    db.add(post)
    try:
        db.commit()
    except Exception:
        delete_media(image_path)
        raise
    db.refresh(post)
    post.author = user
    return PostOut.of(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, user: CurrentUser, db: DbSession) -> None:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    if post.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own posts")
    image_path = post.image_path
    db.delete(post)
    db.commit()
    delete_media(image_path)
