"""add quarter and quarter_users

Revision ID: b656d6bc7138
Revises: 12ce6dda9bc2
Create Date: 2026-06-25 19:14:51.355772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b656d6bc7138'
down_revision: Union[str, None] = '12ce6dda9bc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'quarter',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('quarter_type', sa.String(length=2), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('waterpolo_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('swimming_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['company.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_quarter_id'), 'quarter', ['id'], unique=False)

    op.create_table(
        'quarter_users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('quarter_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type_of_training', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['quarter_id'], ['quarter.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('quarter_id', 'user_id'),
    )
    op.create_index(op.f('ix_quarter_users_id'), 'quarter_users', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_quarter_users_id'), table_name='quarter_users')
    op.drop_table('quarter_users')
    op.drop_index(op.f('ix_quarter_id'), table_name='quarter')
    op.drop_table('quarter')
