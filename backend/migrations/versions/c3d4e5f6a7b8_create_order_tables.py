"""create_order_tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-23 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'c3d4e5f6a7b8'
down_revision: str | Sequence[str] | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # system_settings (referenced by orders for payment info)
    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('key'),
    )
    op.bulk_insert(
        sa.table(
            'system_settings',
            sa.column('key', sa.String),
            sa.column('value', sa.Text),
        ),
        [
            {'key': 'bank_account_number', 'value': ''},
            {'key': 'bank_name', 'value': ''},
            {'key': 'bank_account_name', 'value': ''},
            {'key': 'payment_absolute_deadline_hours', 'value': '48'},
        ],
    )

    # admin_notifications
    op.create_table(
        'admin_notifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('reference_type', sa.String(), nullable=True),
        sa.Column('reference_id', sa.UUID(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('requires_action', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # cart_items
    op.create_table(
        'cart_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('product_variant_id', sa.UUID(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['product_variant_id'], ['product_variants.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # order_number sequence
    op.execute("CREATE SEQUENCE IF NOT EXISTS order_number_seq START 1")

    # orders
    op.create_table(
        'orders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('order_number', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'pending_payment', 'payment_expired', 'paid', 'processing',
                'shipped', 'completed', 'cancelled', 'refund_processing',
                'refunded', 'partially_refunded',
                name='orderstatusenum',
            ),
            nullable=False,
            server_default='pending_payment',
        ),
        sa.Column('subtotal', sa.Numeric(10, 2), nullable=False),
        sa.Column('discount_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column(
            'discount_source',
            sa.Enum('coupon', 'auto_checkout', name='discountsourceenum'),
            nullable=True,
        ),
        sa.Column('auto_checkout_config_id', sa.UUID(), nullable=True),
        sa.Column('shipping_fee', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('total', sa.Numeric(10, 2), nullable=False),
        sa.Column('user_coupon_id', sa.UUID(), nullable=True),
        sa.Column(
            'shipping_type',
            sa.Enum('home', 'seven_eleven', 'family_mart', name='shippingtypeenum'),
            nullable=False,
        ),
        sa.Column(
            'shipping_preference',
            sa.Enum('together', 'separate', name='shippingpreferenceenum'),
            nullable=True,
        ),
        sa.Column('shipping_snapshot', JSONB(), nullable=False),
        sa.Column('payment_deadline', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('paid_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            'cancel_reason_code',
            sa.Enum(
                'payment_expired', 'customer_cancelled', 'admin_cancelled',
                name='cancelreasoncodeenum',
            ),
            nullable=True,
        ),
        sa.Column('cancel_reason_note', sa.Text(), nullable=True),
        sa.Column('refund_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('refunded_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('refund_confirmed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('customer_notes', sa.Text(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['auto_checkout_config_id'], ['coupon_configs.id']),
        sa.ForeignKeyConstraint(['user_coupon_id'], ['user_coupons.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_number'),
    )
    op.create_index('ix_orders_user_id_status', 'orders', ['user_id', 'status'])
    op.create_index('ix_orders_status_payment_deadline', 'orders', ['status', 'payment_deadline'])

    # order_items
    op.create_table(
        'order_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('product_variant_id', sa.UUID(), nullable=True),
        sa.Column('custom_request_id', sa.UUID(), nullable=True),  # FK added in Module 10
        sa.Column('production_job_id', sa.UUID(), nullable=True),
        sa.Column('product_title_snapshot', sa.String(), nullable=False),
        sa.Column('variant_spec_snapshot', JSONB(), nullable=False),
        sa.Column('unit_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('fulfilled_qty', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('preorder_qty', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_returned', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['product_variant_id'], ['product_variants.id']),
        sa.ForeignKeyConstraint(['production_job_id'], ['production_jobs.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # shipments
    op.create_table(
        'shipments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column(
            'shipment_type',
            sa.Enum('fulfilled', 'preorder', name='shipmenttypeenum'),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.Enum('pending', 'shipped', 'delivered', name='shipmentstatusenum'),
            nullable=False,
            server_default='pending',
        ),
        sa.Column('tracking_number', sa.String(), nullable=True),
        sa.Column('ecpay_logistics_id', sa.String(), nullable=True),
        sa.Column('shipped_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # production_progress
    op.create_table(
        'production_progress',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('order_item_id', sa.UUID(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'pending', 'in_production', 'manufacturing', 'packaging',
                'ready_to_ship', 'shipped',
                name='productionprogressstatusenum',
            ),
            nullable=False,
            server_default='pending',
        ),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['order_item_id'], ['order_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # payment_submissions
    op.create_table(
        'payment_submissions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('is_flagged', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('transfer_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('transfer_date', sa.Date(), nullable=False),
        sa.Column('transfer_time', sa.Time(), nullable=False),
        sa.Column('account_last5', sa.String(5), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Deferred FKs from discount module (user_coupons → orders)
    op.create_foreign_key(
        'fk_user_coupons_order',
        'user_coupons', 'orders',
        ['used_in_order_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_user_coupons_source_order',
        'user_coupons', 'orders',
        ['source_order_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_user_coupons_source_order', 'user_coupons', type_='foreignkey')
    op.drop_constraint('fk_user_coupons_order', 'user_coupons', type_='foreignkey')
    op.drop_table('payment_submissions')
    op.drop_table('production_progress')
    op.drop_table('shipments')
    op.drop_table('order_items')
    op.drop_index('ix_orders_status_payment_deadline', table_name='orders')
    op.drop_index('ix_orders_user_id_status', table_name='orders')
    op.drop_table('orders')
    op.execute("DROP SEQUENCE IF EXISTS order_number_seq")
    op.drop_table('cart_items')
    op.drop_table('admin_notifications')
    op.drop_table('system_settings')
    op.execute("DROP TYPE IF EXISTS productionprogressstatusenum")
    op.execute("DROP TYPE IF EXISTS shipmentstatusenum")
    op.execute("DROP TYPE IF EXISTS shipmenttypeenum")
    op.execute("DROP TYPE IF EXISTS cancelreasoncodeenum")
    op.execute("DROP TYPE IF EXISTS shippingpreferenceenum")
    op.execute("DROP TYPE IF EXISTS shippingtypeenum")
    op.execute("DROP TYPE IF EXISTS discountsourceenum")
    op.execute("DROP TYPE IF EXISTS orderstatusenum")
