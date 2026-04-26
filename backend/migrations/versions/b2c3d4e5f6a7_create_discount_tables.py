"""create_discount_tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-23 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'b2c3d4e5f6a7'
down_revision: str | Sequence[str] | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'coupon_configs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column(
            'coupon_type',
            sa.Enum('new_user', 'spend_reward', 'returning_loyal', 'manual', 'auto_checkout',
                    name='coupontypeenum'),
            nullable=False,
        ),
        sa.Column(
            'discount_type',
            sa.Enum('percentage', 'fixed', name='discounttypeenum'),
            nullable=False,
        ),
        sa.Column('discount_value', sa.Numeric(10, 2), nullable=False),
        sa.Column('min_purchase', sa.Numeric(10, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('params', JSONB(), nullable=False, server_default='{}'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_coupon_configs_coupon_type_unique',
        'coupon_configs',
        ['coupon_type'],
        unique=True,
        postgresql_where=sa.text("coupon_type != 'auto_checkout'"),
    )

    op.create_table(
        'promo_codes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column(
            'discount_type',
            sa.Enum('percentage', 'fixed', name='discounttypeenum'),
            nullable=False,
        ),
        sa.Column('discount_value', sa.Numeric(10, 2), nullable=False),
        sa.Column('min_purchase', sa.Numeric(10, 2), nullable=True),
        sa.Column('start_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('end_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('max_total_uses', sa.Integer(), nullable=True),
        sa.Column('max_per_user', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('total_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    op.create_table(
        'user_coupons',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('coupon_config_id', sa.UUID(), nullable=True),
        sa.Column('promo_code_id', sa.UUID(), nullable=True),
        sa.Column(
            'discount_type',
            sa.Enum('percentage', 'fixed', name='discounttypeenum'),
            nullable=False,
        ),
        sa.Column('discount_value', sa.Numeric(10, 2), nullable=False),
        sa.Column('min_purchase', sa.Numeric(10, 2), nullable=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('used_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('used_in_order_id', sa.UUID(), nullable=True),
        sa.Column('source_order_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            'coupon_config_id IS NOT NULL OR promo_code_id IS NOT NULL',
            name='ck_user_coupons_config_or_promo',
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['coupon_config_id'], ['coupon_configs.id']),
        sa.ForeignKeyConstraint(['promo_code_id'], ['promo_codes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_coupons_user_id_is_used', 'user_coupons', ['user_id', 'is_used'])
    op.create_index('ix_user_coupons_source_order_id', 'user_coupons', ['source_order_id'])
    op.create_index('ix_user_coupons_used_in_order_id', 'user_coupons', ['used_in_order_id'])


def downgrade() -> None:
    op.drop_index('ix_user_coupons_used_in_order_id', table_name='user_coupons')
    op.drop_index('ix_user_coupons_source_order_id', table_name='user_coupons')
    op.drop_index('ix_user_coupons_user_id_is_used', table_name='user_coupons')
    op.drop_table('user_coupons')
    op.drop_table('promo_codes')
    op.drop_index('ix_coupon_configs_coupon_type_unique', table_name='coupon_configs')
    op.drop_table('coupon_configs')
    op.execute("DROP TYPE IF EXISTS coupontypeenum")
    op.execute("DROP TYPE IF EXISTS discounttypeenum")
