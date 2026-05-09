"""custom_requests 加 quoted_production_job_id

報價綁定 admin 挑選的特定 production_job：
- 之前邏輯：preview-watermark / quote_summary 都用「最新一筆有 filled_template_url 的 job」
  → admin 跑了 5 個版本只想用第 2 個時無法指定
- 改成 admin 在 QuoteDialog 選一個 completed job，把 job_id 寫入此欄位
  之後客戶看到的預覽 + 規格都從該 job 拿

向後相容：欄位 nullable，舊的 quote 仍 fallback 到「最新一筆 filled」。

Revision ID: n4i5j6k7l8m9
Revises: m3h4i5j6k7l8
Create Date: 2026-05-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "n4i5j6k7l8m9"
down_revision: str | None = "m3h4i5j6k7l8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "custom_requests",
        sa.Column(
            "quoted_production_job_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("production_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("custom_requests", "quoted_production_job_id")
