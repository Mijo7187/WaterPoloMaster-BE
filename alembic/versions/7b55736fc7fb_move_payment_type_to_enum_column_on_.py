"""move payment_type to enum column on payment

Revision ID: 7b55736fc7fb
Revises: c8d9e0f1a2b3
Create Date: 2026-07-06 16:14:44.565516

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7b55736fc7fb'
down_revision: Union[str, None] = 'c8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The paymenttypecode native enum already exists in the DB (created by
# 9989f889b9ad_payment_type_enum_rework), so reuse it with create_type=False.
paymenttypecode = postgresql.ENUM(
    'USER_QUARTERLY_FEE', 'USER_TOURNAMENT_FEE', 'CLUB_TOURNAMENT_POOL',
    'CLUB_SALARY_USER', 'CLUB_TRAINING_POOL',
    name='paymenttypecode', create_type=False,
)


def upgrade() -> None:
    # 1. Add the new enum column nullable so existing rows survive.
    op.add_column('payment', sa.Column('payment_type', paymenttypecode, nullable=True))

    # 2. Backfill it from the payment_type reference table before dropping it.
    op.execute(
        "UPDATE payment SET payment_type = pt.code "
        "FROM payment_type pt WHERE pt.id = payment.payment_type_id"
    )

    # 3. Enforce NOT NULL now that every row has a value.
    op.alter_column('payment', 'payment_type', nullable=False)

    # 4. Drop the old FK column and the now-redundant reference table.
    op.drop_constraint('payment_payment_type_id_fkey', 'payment', type_='foreignkey')
    op.drop_column('payment', 'payment_type_id')
    op.drop_index('ix_payment_type_id', table_name='payment_type')
    op.drop_table('payment_type')


def downgrade() -> None:
    # Recreate the reference table (empty — best-effort, data is not restored).
    op.create_table('payment_type',
    sa.Column('name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('active', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('code', paymenttypecode, autoincrement=False, nullable=False),
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('sender_type', postgresql.ENUM('USER', 'COMPANY', name='walletownertype'), autoincrement=False, nullable=False),
    sa.Column('receiver_type', postgresql.ENUM('USER', 'COMPANY', name='walletownertype'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name='payment_type_pkey')
    )
    op.create_index('ix_payment_type_id', 'payment_type', ['id'], unique=False)

    # Re-add the FK column nullable (ids can't be reconstructed from the enum).
    op.add_column('payment', sa.Column('payment_type_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key('payment_payment_type_id_fkey', 'payment', 'payment_type', ['payment_type_id'], ['id'])
    op.drop_column('payment', 'payment_type')
