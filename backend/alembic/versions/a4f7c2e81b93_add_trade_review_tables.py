"""add_trade_review_tables

Revision ID: a4f7c2e81b93
Revises: 9863acc83e39
Create Date: 2026-06-15 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4f7c2e81b93"
down_revision: Union[str, None] = "9863acc83e39"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 用户复盘记录
    op.create_table(
        "trade_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("preview", sa.String(200), nullable=True),
        sa.Column("message_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # 复盘对话消息
    op.create_table(
        "trade_review_messages",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("trade_reviews.id"), nullable=False, index=True),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("trade_review_messages")
    op.drop_table("trade_reviews")
