"""create_shipping_profiles

Revision ID: 4aaee5f4f879
Revises: 2e491a112343
Create Date: 2026-04-19 20:23:43.802968

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4aaee5f4f879'
down_revision: str | Sequence[str] | None = '2e491a112343'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'shipping_profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('shipping_type', sa.Enum('home', 'seven_eleven', 'family_mart', name='shippingtypeenum'), nullable=False),
        sa.Column('recipient_name', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('district', sa.String(), nullable=True),
        sa.Column('address_detail', sa.String(), nullable=True),
        sa.Column('store_id', sa.String(), nullable=True),
        sa.Column('store_name', sa.String(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('shipping_profiles')
    op.execute("DROP TYPE IF EXISTS shippingtypeenum")
