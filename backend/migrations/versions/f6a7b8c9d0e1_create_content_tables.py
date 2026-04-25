"""create_content_tables (static_pages, case_categories, custom_cases)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-26 02:00:00.000000

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DIFFICULTIES = ('beginner', 'elementary', 'intermediate', 'advanced')


def upgrade() -> None:
    static_pages = op.create_table(
        'static_pages',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )

    op.create_table(
        'case_categories',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    op.create_table(
        'custom_cases',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('image_url', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('canvas_w_cm', sa.Integer(), nullable=True),
        sa.Column('canvas_h_cm', sa.Integer(), nullable=True),
        sa.Column('difficulty',
                  sa.Enum(*_DIFFICULTIES, name='difficultyenum', create_type=False),
                  nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['category_id'], ['case_categories.id'], ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    # Seed default page slugs (parameterized via op.bulk_insert — no string interpolation)
    op.bulk_insert(
        static_pages,
        [
            {"id": uuid.uuid4(), "slug": "size_guide", "title": "尺寸指南",
             "content": "（請於後台編輯內容）"},
            {"id": uuid.uuid4(), "slug": "shipping", "title": "運送說明",
             "content": "（請於後台編輯內容）"},
            {"id": uuid.uuid4(), "slug": "custom_process", "title": "客製流程",
             "content": "（請於後台編輯內容）"},
            {"id": uuid.uuid4(), "slug": "pricing_reference", "title": "定價參考",
             "content": "（請於後台編輯內容）"},
            {"id": uuid.uuid4(), "slug": "refund_policy", "title": "退換貨政策",
             "content": "（請於後台編輯內容）"},
        ],
    )


def downgrade() -> None:
    op.drop_table('custom_cases')
    op.drop_table('case_categories')
    op.drop_table('static_pages')
