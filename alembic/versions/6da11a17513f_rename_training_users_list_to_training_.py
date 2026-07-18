"""rename training_users_list to training_users, drop orphan training_users

Revision ID: 6da11a17513f
Revises: 7b55736fc7fb
Create Date: 2026-07-06 16:24:28.371650

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6da11a17513f'
down_revision: Union[str, None] = '7b55736fc7fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the orphan legacy association table (no model maps to it, 0 rows).
    op.drop_table('training_users')

    # 2. Rename the active table (preserves its rows) and its owned objects so the
    #    schema matches what the TrainingUsers model / a fresh create_all produce.
    op.rename_table('training_users_list', 'training_users')
    op.execute('ALTER INDEX ix_training_users_list_id RENAME TO ix_training_users_id')
    op.execute('ALTER TABLE training_users RENAME CONSTRAINT training_users_list_pkey TO training_users_pkey')
    op.execute('ALTER TABLE training_users RENAME CONSTRAINT training_users_list_training_id_user_id_key TO training_users_training_id_user_id_key')
    op.execute('ALTER TABLE training_users RENAME CONSTRAINT training_users_list_training_id_fkey TO training_users_training_id_fkey')
    op.execute('ALTER TABLE training_users RENAME CONSTRAINT training_users_list_user_id_fkey TO training_users_user_id_fkey')
    op.execute('ALTER SEQUENCE training_users_list_id_seq RENAME TO training_users_id_seq')


def downgrade() -> None:
    # Reverse the rename of the active table and its owned objects.
    op.execute('ALTER SEQUENCE training_users_id_seq RENAME TO training_users_list_id_seq')
    op.execute('ALTER TABLE training_users RENAME CONSTRAINT training_users_user_id_fkey TO training_users_list_user_id_fkey')
    op.execute('ALTER TABLE training_users RENAME CONSTRAINT training_users_training_id_fkey TO training_users_list_training_id_fkey')
    op.execute('ALTER TABLE training_users RENAME CONSTRAINT training_users_training_id_user_id_key TO training_users_list_training_id_user_id_key')
    op.execute('ALTER TABLE training_users RENAME CONSTRAINT training_users_pkey TO training_users_list_pkey')
    op.execute('ALTER INDEX ix_training_users_id RENAME TO ix_training_users_list_id')
    op.rename_table('training_users', 'training_users_list')

    # Recreate the orphan legacy association table (empty).
    op.create_table('training_users',
        sa.Column('training_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['training_id'], ['training.id'], name='training_users_training_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='training_users_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('training_id', 'user_id', name='training_users_pkey')
    )
