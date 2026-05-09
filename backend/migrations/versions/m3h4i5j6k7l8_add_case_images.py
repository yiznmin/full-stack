"""add case_images table

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-05-09

新增多圖支援：custom_cases 之前只能存單一 image_url，
admin 後台需要可以掛多張、決定順序（封面 = sort_order=0）。
保留 custom_cases.image_url 作為「主圖快取 / 向後相容」，
service 層儲存時會把第一張同步進去。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'm3h4i5j6k7l8'
down_revision: str | Sequence[str] | None = 'l2g3h4i5j6k7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'case_images',
        sa.Column(
            'id', sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'case_id', sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey('custom_cases.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('image_url', sa.String(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column(
            'created_at', sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index('idx_case_images_case_id_sort', 'case_images', ['case_id', 'sort_order'])

    # Backfill: 把現有 custom_cases.image_url 灌進 case_images（sort_order=0）
    # 跳過 image_url 為空的案例
    op.execute(
        """
        INSERT INTO case_images (id, case_id, image_url, sort_order)
        SELECT gen_random_uuid(), id, image_url, 0
        FROM custom_cases
        WHERE image_url IS NOT NULL AND image_url <> ''
        """
    )


def downgrade() -> None:
    op.drop_index('idx_case_images_case_id_sort', table_name='case_images')
    op.drop_table('case_images')
