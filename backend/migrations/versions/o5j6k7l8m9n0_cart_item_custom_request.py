"""cart_items 加 custom_request_id + production_job_id；product_variant_id 改 nullable

新流程：客戶 confirm quote 不再直接建 Order，改加進 cart 跟一般商品合買。
cart_item 二選一：
- 一般商品 → product_variant_id 有值
- 客製商品 → custom_request_id + production_job_id 有值

免運門檻計算時排除客製 line（service 層處理）。

Revision ID: o5j6k7l8m9n0
Revises: n4i5j6k7l8m9
Create Date: 2026-05-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o5j6k7l8m9n0"
down_revision: str | None = "n4i5j6k7l8m9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "cart_items", "product_variant_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column(
        "cart_items",
        sa.Column(
            "custom_request_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("custom_requests.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "cart_items",
        sa.Column(
            "production_job_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("production_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("cart_items", "production_job_id")
    op.drop_column("cart_items", "custom_request_id")
    op.alter_column(
        "cart_items", "product_variant_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
