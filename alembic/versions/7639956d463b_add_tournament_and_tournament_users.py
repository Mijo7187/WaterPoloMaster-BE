"""add tournament and tournament_users

Revision ID: 7639956d463b
Revises: b656d6bc7138
Create Date: 2026-06-26 14:30:40.047386

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7639956d463b'
down_revision: Union[str, None] = 'b656d6bc7138'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tournament',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('pool_id', sa.Integer(), nullable=False),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('to_date', sa.Date(), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['company.id']),
        sa.ForeignKeyConstraint(['pool_id'], ['company.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tournament_id'), 'tournament', ['id'], unique=False)

    op.create_table(
        'tournament_users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournament.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['company.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tournament_id', 'user_id'),
    )
    op.create_index(op.f('ix_tournament_users_id'), 'tournament_users', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tournament_users_id'), table_name='tournament_users')
    op.drop_table('tournament_users')
    op.drop_index(op.f('ix_tournament_id'), table_name='tournament')
    op.drop_table('tournament')
