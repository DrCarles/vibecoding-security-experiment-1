"""Initial schema: users and posts.

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("username", sa.String(30), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("age", sa.SmallInteger(), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("display_name", sa.String(50), nullable=False),
        sa.Column("avatar_path", sa.String(255), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("age BETWEEN 13 AND 130", name="ck_users_age"),
    )
    op.create_index("ux_users_email", "users", ["email"], unique=True)
    op.create_index("ux_users_username", "users", ["username"], unique=True)

    op.create_table(
        "posts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("author_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.String(280), nullable=False, server_default=""),
        sa.Column("image_path", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("char_length(body) > 0 OR image_path IS NOT NULL", name="ck_posts_not_empty"),
    )
    op.create_index("ix_posts_author_id_id", "posts", ["author_id", "id"])


def downgrade() -> None:
    op.drop_table("posts")
    op.drop_table("users")
