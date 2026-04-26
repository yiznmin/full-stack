"""create print_batches + print_batch_items

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-04-26 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'i9d0e1f2g3h4'
down_revision: str | Sequence[str] | None = 'h8c9d0e1f2g3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_BATCH_STATUSES = ('draft', 'finalized')
_ITEM_SOURCES = ('order_item', 'standalone')


def upgrade() -> None:
    op.create_table(
        'print_batches',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'status',
            sa.Enum(*_BATCH_STATUSES, name='printbatchstatusenum'),
            nullable=False, server_default='draft',
        ),
        sa.Column('total_inch_count', sa.Numeric(10, 2), nullable=False),
        sa.Column('billable_inch_count', sa.Numeric(10, 2), nullable=False),
        sa.Column('print_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('cut_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('total_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('pdf_url', sa.String(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column(
            'created_by_user_id',
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            'created_at', sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column('finalized_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'print_batch_items',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'print_batch_id',
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            'source_type',
            sa.Enum(*_ITEM_SOURCES, name='printbatchitemsourceenum'),
            nullable=False,
        ),
        sa.Column(
            'source_order_item_id',
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            'production_job_id',
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('inch_per_unit', sa.Numeric(10, 4), nullable=False),
        sa.Column('canvas_w_cm', sa.Numeric(6, 1), nullable=False),
        sa.Column('canvas_h_cm', sa.Numeric(6, 1), nullable=False),
        sa.ForeignKeyConstraint(
            ['print_batch_id'], ['print_batches.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['source_order_item_id'], ['order_items.id'], ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(['production_job_id'], ['production_jobs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('quantity >= 1', name='ck_print_batch_item_qty_positive'),
    )

    op.create_index(
        'ix_print_batches_status_created',
        'print_batches',
        ['status', sa.text('created_at DESC')],
    )


def downgrade() -> None:
    op.drop_index('ix_print_batches_status_created', table_name='print_batches')
    op.drop_table('print_batch_items')
    op.drop_table('print_batches')
    sa.Enum(name='printbatchitemsourceenum').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='printbatchstatusenum').drop(op.get_bind(), checkfirst=False)
