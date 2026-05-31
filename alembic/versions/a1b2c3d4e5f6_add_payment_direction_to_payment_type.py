"""add_payment_direction_and_wallet_payment_tables

Revision ID: a1b2c3d4e5f6
Revises: aa593ad8fbcc
Create Date: 2026-05-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'aa593ad8fbcc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

payment_direction_enum = sa.Enum('C_C', 'U_C', 'C_U', name='paymentdirection')


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # ── paymentdirection enum ────────────────────────────────────
    if bind.dialect.name == 'postgresql':
        payment_direction_enum.create(bind, checkfirst=True)

    # ── payment_type: add missing columns ────────────────────────
    existing_cols = {col['name'] for col in inspector.get_columns('payment_type')}

    if 'payment_direction' not in existing_cols:
        op.add_column(
            'payment_type',
            sa.Column('payment_direction', payment_direction_enum, nullable=True),
        )
    if 'created_at' not in existing_cols:
        op.add_column(
            'payment_type',
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        )
    if 'updated_at' not in existing_cols:
        op.add_column(
            'payment_type',
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        )

    # ── wallet ───────────────────────────────────────────────────
    if not inspector.has_table('wallet'):
        op.create_table(
            'wallet',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('owner_type', sa.Enum('user', 'company', name='ownertype'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.PrimaryKeyConstraint('id'),
        )

    # ── payment ──────────────────────────────────────────────────
    if not inspector.has_table('payment'):
        op.create_table(
            'payment',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('sender_wallet_id', sa.UUID(), nullable=False),
            sa.Column('receiver_wallet_id', sa.UUID(), nullable=False),
            sa.Column('payment_type_id', sa.Integer(), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('status',
                      sa.Enum('pending', 'completed', 'failed', 'refunded', name='paymentstatus'),
                      nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.ForeignKeyConstraint(['sender_wallet_id'], ['wallet.id']),
            sa.ForeignKeyConstraint(['receiver_wallet_id'], ['wallet.id']),
            sa.ForeignKeyConstraint(['payment_type_id'], ['payment_type.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('idx_payment_sender', 'payment', ['sender_wallet_id', 'status'])
        op.create_index('idx_payment_receiver', 'payment', ['receiver_wallet_id', 'status'])

    # ── wallet_id on existing tables ─────────────────────────────
    users_cols = {col['name'] for col in inspector.get_columns('users')}
    if 'wallet_id' not in users_cols:
        op.add_column('users', sa.Column('wallet_id', sa.UUID(), nullable=True))
        op.create_foreign_key('fk_users_wallet_id', 'users', 'wallet', ['wallet_id'], ['id'])

    company_cols = {col['name'] for col in inspector.get_columns('company')}
    if 'wallet_id' not in company_cols:
        op.add_column('company', sa.Column('wallet_id', sa.UUID(), nullable=True))
        op.create_foreign_key('fk_company_wallet_id', 'company', 'wallet', ['wallet_id'], ['id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if 'wallet_id' in {col['name'] for col in inspector.get_columns('company')}:
        op.drop_constraint('fk_company_wallet_id', 'company', type_='foreignkey')
        op.drop_column('company', 'wallet_id')

    if 'wallet_id' in {col['name'] for col in inspector.get_columns('users')}:
        op.drop_constraint('fk_users_wallet_id', 'users', type_='foreignkey')
        op.drop_column('users', 'wallet_id')

    if inspector.has_table('payment'):
        op.drop_index('idx_payment_receiver', table_name='payment')
        op.drop_index('idx_payment_sender', table_name='payment')
        op.drop_table('payment')

    if inspector.has_table('wallet'):
        op.drop_table('wallet')

    payment_type_cols = {col['name'] for col in inspector.get_columns('payment_type')}
    if 'updated_at' in payment_type_cols:
        op.drop_column('payment_type', 'updated_at')
    if 'created_at' in payment_type_cols:
        op.drop_column('payment_type', 'created_at')
    if 'payment_direction' in payment_type_cols:
        op.drop_column('payment_type', 'payment_direction')

    if bind.dialect.name == 'postgresql':
        sa.Enum(name='paymentstatus').drop(bind, checkfirst=True)
        sa.Enum(name='ownertype').drop(bind, checkfirst=True)
        payment_direction_enum.drop(bind, checkfirst=True)
