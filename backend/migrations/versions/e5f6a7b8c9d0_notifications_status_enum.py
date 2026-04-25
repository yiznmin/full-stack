"""notifications: is_completed boolean → status enum

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-25 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type and add status column with default
    sa.Enum(
        'unhandled', 'in_progress', 'completed',
        name='notificationstatusenum',
    ).create(op.get_bind(), checkfirst=False)

    op.add_column(
        'admin_notifications',
        sa.Column(
            'status',
            sa.Enum(
                'unhandled', 'in_progress', 'completed',
                name='notificationstatusenum', create_type=False,
            ),
            nullable=False,
            server_default='unhandled',
        ),
    )

    # Back-fill: any existing is_completed=true → status=completed
    op.execute(
        "UPDATE admin_notifications SET status = 'completed' "
        "WHERE is_completed = true"
    )

    op.drop_column('admin_notifications', 'is_completed')

    op.create_index(
        'ix_admin_notifications_status_created',
        'admin_notifications',
        ['status', sa.text('created_at DESC')],
    )
    op.create_index(
        'ix_admin_notifications_reference',
        'admin_notifications',
        ['reference_type', 'reference_id'],
    )
    op.create_index(
        'ix_admin_notifications_type_status_ref',
        'admin_notifications',
        ['type', 'status', 'reference_id'],
    )

    # Partial unique index — guarantees at most one ACTIVE stock_shortage per
    # (reference_type, reference_id), enabling INSERT ... ON CONFLICT DO UPDATE
    # to be race-safe (per admin_notifications.md §73).
    op.execute(
        "CREATE UNIQUE INDEX uq_active_stock_shortage_per_ref "
        "ON admin_notifications (reference_type, reference_id) "
        "WHERE type = 'stock_shortage' "
        "AND status IN ('unhandled', 'in_progress')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_active_stock_shortage_per_ref")
    op.drop_index('ix_admin_notifications_type_status_ref', table_name='admin_notifications')
    op.drop_index('ix_admin_notifications_reference', table_name='admin_notifications')
    op.drop_index('ix_admin_notifications_status_created', table_name='admin_notifications')

    op.add_column(
        'admin_notifications',
        sa.Column(
            'is_completed', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.execute(
        "UPDATE admin_notifications SET is_completed = true WHERE status = 'completed'"
    )
    op.drop_column('admin_notifications', 'status')
    sa.Enum(name='notificationstatusenum').drop(op.get_bind(), checkfirst=False)
