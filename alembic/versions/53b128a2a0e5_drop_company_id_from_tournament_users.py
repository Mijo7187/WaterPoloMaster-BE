"""drop company_id from tournament_users

Revision ID: 53b128a2a0e5
Revises: 7639956d463b
Create Date: 2026-06-26 17:12:07.223605

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53b128a2a0e5'
down_revision: Union[str, None] = '7639956d463b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('tournament_users_company_id_fkey', 'tournament_users', type_='foreignkey')
    op.drop_column('tournament_users', 'company_id')


def downgrade() -> None:
    op.add_column('tournament_users', sa.Column('company_id', sa.INTEGER(), autoincrement=False, nullable=False))
    op.create_foreign_key('tournament_users_company_id_fkey', 'tournament_users', 'company', ['company_id'], ['id'])
