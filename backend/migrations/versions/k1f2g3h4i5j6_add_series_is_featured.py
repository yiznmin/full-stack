"""add product_series.is_featured

Revision ID: k1f2g3h4i5j6
Revises: 76e1a6c1267e
Create Date: 2026-05-05 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'k1f2g3h4i5j6'
down_revision: str | Sequence[str] | None = '76e1a6c1267e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'product_series',
        sa.Column(
            'is_featured',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )


def downgrade() -> None:
    op.drop_column('product_series', 'is_featured')
