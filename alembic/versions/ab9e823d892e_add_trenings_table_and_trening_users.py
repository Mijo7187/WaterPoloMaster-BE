"""add_trainings_table_and_training_users

Revision ID: ab9e823d892e
Revises: 7d4a78e333fa
Create Date: 2026-03-27 12:42:31.622952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab9e823d892e'
down_revision: Union[str, None] = '7d4a78e333fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename tables
    op.rename_table('trenings', 'trainings')
    op.rename_table('trening_users', 'training_users')

    # Rename columns in trainings
    op.alter_column('trainings', 'start_trening_date_time', new_column_name='start_training_date_time')
    op.alter_column('trainings', 'end_trening_date_time', new_column_name='end_training_date_time')

    # Rename column in training_users
    op.alter_column('training_users', 'trening_id', new_column_name='training_id')

    # Add company_id to trainings
    op.add_column('trainings', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_trainings_company_id', 'trainings', 'companies', ['company_id'], ['id'])
    # Make company_id NOT NULL after setting defaults if needed
    op.alter_column('trainings', 'company_id', nullable=False)


def downgrade() -> None:
    op.drop_constraint('fk_trainings_company_id', 'trainings', type_='foreignkey')
    op.drop_column('trainings', 'company_id')

    op.alter_column('training_users', 'training_id', new_column_name='trening_id')
    op.alter_column('trainings', 'start_training_date_time', new_column_name='start_trening_date_time')
    op.alter_column('trainings', 'end_training_date_time', new_column_name='end_trening_date_time')

    op.rename_table('training_users', 'trening_users')
    op.rename_table('trainings', 'trenings')
    op.drop_table('trenings')
