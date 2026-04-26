"""create_custom_tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-25 00:00:00.000000

"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: str | Sequence[str] | None = 'c3d4e5f6a7b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_REQUEST_TYPES = ('custom_photo', 'custom_spec')
_REQUEST_STATUSES = (
    'quote_pending', 'negotiating', 'quote_sent', 'draft_revision',
    'quote_confirmed', 'quote_rejected', 'quote_expired',
)
_SENDER_TYPES = ('admin', 'customer')
_DIFFICULTIES = ('beginner', 'elementary', 'intermediate', 'advanced')
_DETAILS = ('rough', 'standard', 'detailed', 'premium')


def upgrade() -> None:
    op.create_table(
        'custom_requests',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_type',
                  sa.Enum(*_REQUEST_TYPES, name='customrequesttypeenum'), nullable=False),
        sa.Column('status',
                  sa.Enum(*_REQUEST_STATUSES, name='customrequeststatusenum'),
                  nullable=False, server_default='quote_pending'),
        sa.Column('photo_url', sa.String(), nullable=True),
        sa.Column('ref_product_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('canvas_w_cm', sa.Integer(), nullable=True),
        sa.Column('canvas_h_cm', sa.Integer(), nullable=True),
        sa.Column('difficulty',
                  sa.Enum(*_DIFFICULTIES, name='difficultyenum', create_type=False),
                  nullable=True),
        sa.Column('detail',
                  sa.Enum(*_DETAILS, name='detailenum', create_type=False), nullable=True),
        sa.Column('customer_notes', sa.Text(), nullable=True),
        sa.Column('quoted_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('quote_token', sa.String(), nullable=True),
        sa.Column('quote_expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('is_extended', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('revision_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parent_request_id',
                  sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('order_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('quoted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['ref_product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['parent_request_id'], ['custom_requests.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('quote_token'),
    )
    op.create_index(
        'ix_custom_requests_user_status',
        'custom_requests', ['user_id', 'status'],
    )
    op.create_index(
        'ix_custom_requests_quote_expires',
        'custom_requests', ['quote_expires_at'],
    )

    op.create_table(
        'custom_request_messages',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_id',
                  sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_type',
                  sa.Enum(*_SENDER_TYPES, name='messagesendertypeenum'),
                  nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['request_id'], ['custom_requests.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'custom_photo_prices',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('canvas_w', sa.Integer(), nullable=False),
        sa.Column('canvas_h', sa.Integer(), nullable=False),
        sa.Column('difficulty',
                  sa.Enum(*_DIFFICULTIES, name='difficultyenum', create_type=False),
                  nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('canvas_w', 'canvas_h', 'difficulty'),
    )

    op.create_table(
        'custom_photo_surcharges',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    canvas_sizes_t = op.create_table(
        'canvas_sizes',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('canvas_w_cm', sa.Integer(), nullable=False),
        sa.Column('canvas_h_cm', sa.Integer(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('canvas_w_cm', 'canvas_h_cm'),
    )

    # Now back-fill FK constraints on order_items.custom_request_id
    # and production_jobs.custom_request_id (columns existed but FK deferred)
    op.create_foreign_key(
        'fk_order_items_custom_request',
        'order_items', 'custom_requests',
        ['custom_request_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_production_jobs_custom_request',
        'production_jobs', 'custom_requests',
        ['custom_request_id'], ['id'],
    )

    # Seed system_settings.quote_reply_days if not present
    op.execute(
        "INSERT INTO system_settings (key, value) VALUES ('quote_reply_days', '3') "
        "ON CONFLICT (key) DO NOTHING"
    )

    # Seed canvas_sizes (17 standard sizes per pricing_formula.md) — parameterized
    seeds = [
        (20, 20, "20×20 cm", 1),
        (30, 30, "30×30 cm", 2),
        (30, 40, "30×40 cm", 3),
        (40, 30, "40×30 cm", 4),
        (30, 50, "30×50 cm", 5),
        (40, 40, "40×40 cm", 6),
        (50, 30, "50×30 cm", 7),
        (30, 60, "30×60 cm", 8),
        (40, 50, "40×50 cm", 9),
        (50, 40, "50×40 cm", 10),
        (40, 60, "40×60 cm", 11),
        (60, 40, "60×40 cm", 12),
        (50, 50, "50×50 cm", 13),
        (50, 60, "50×60 cm", 14),
        (60, 50, "60×50 cm", 15),
        (60, 60, "60×60 cm", 16),
        (70, 50, "70×50 cm", 17),
    ]
    op.bulk_insert(
        canvas_sizes_t,
        [
            {
                "id": uuid.uuid4(), "canvas_w_cm": w, "canvas_h_cm": h,
                "display_name": name, "sort_order": order,
            }
            for w, h, name, order in seeds
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_production_jobs_custom_request', 'production_jobs', type_='foreignkey'
    )
    op.drop_constraint(
        'fk_order_items_custom_request', 'order_items', type_='foreignkey'
    )
    op.drop_table('canvas_sizes')
    op.drop_table('custom_photo_surcharges')
    op.drop_table('custom_photo_prices')
    op.drop_table('custom_request_messages')
    op.drop_index('ix_custom_requests_quote_expires', table_name='custom_requests')
    op.drop_index('ix_custom_requests_user_status', table_name='custom_requests')
    op.drop_table('custom_requests')
    sa.Enum(name='messagesendertypeenum').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='customrequeststatusenum').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='customrequesttypeenum').drop(op.get_bind(), checkfirst=False)
