"""product_series 加 sample_cover_image_url — 系列專屬 hero 封面圖

對應前端 SeriesDetailPage hero 邏輯。沒設時 fallback 到第一個 product 的 cover_image_url。

Revision ID: q7l8m9n0o1p2
Revises: p6k7l8m9n0o1
Create Date: 2026-05-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "q7l8m9n0o1p2"
down_revision: str | None = "p6k7l8m9n0o1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_series",
        sa.Column("sample_cover_image_url", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product_series", "sample_cover_image_url")
