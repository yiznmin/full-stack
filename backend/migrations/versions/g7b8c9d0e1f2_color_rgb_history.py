"""create physical_color_rgb_history + back-fill initial snapshot

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-26 03:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'g7b8c9d0e1f2'
down_revision: str | Sequence[str] | None = 'f6a7b8c9d0e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'physical_color_rgb_history',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('physical_color_id',
                  sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rgb', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('changed_by_user_id',
                  sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('note', sa.String(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['physical_color_id'], ['physical_colors.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['changed_by_user_id'], ['users.id'], ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_color_rgb_history_color_created',
        'physical_color_rgb_history',
        ['physical_color_id', sa.text('created_at DESC')],
    )

    # Back-fill: for each existing PhysicalColor, INSERT one initial snapshot
    op.execute(
        "INSERT INTO physical_color_rgb_history "
        "(id, physical_color_id, rgb, note, created_at) "
        "SELECT gen_random_uuid(), id, rgb, 'initial (back-filled)', created_at "
        "FROM physical_colors"
    )


def downgrade() -> None:
    op.drop_index(
        'ix_color_rgb_history_color_created',
        table_name='physical_color_rgb_history',
    )
    op.drop_table('physical_color_rgb_history')
