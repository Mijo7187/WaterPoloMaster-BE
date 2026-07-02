"""split_training_datetime_into_date_start_time_end_time

Revision ID: e7ffee1c4922
Revises: 9989f889b9ad
Create Date: 2026-06-15 22:59:45.359871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e7ffee1c4922'
down_revision: Union[str, None] = '9989f889b9ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns as nullable for backfill
    op.add_column('training', sa.Column('training_date', sa.Date(), nullable=True))
    op.add_column('training', sa.Column('start_time', sa.Time(), nullable=True))
    op.add_column('training', sa.Column('end_time', sa.Time(), nullable=True))

    # Backfill: extract date and time parts from the old datetime columns
    op.execute("""
        UPDATE training
        SET training_date = start_training_date_time::date,
            start_time    = start_training_date_time::time,
            end_time      = end_training_date_time::time
        WHERE start_training_date_time IS NOT NULL
    """)

    # Enforce NOT NULL now that every row has values
    op.alter_column('training', 'training_date', nullable=False)
    op.alter_column('training', 'start_time', nullable=False)
    op.alter_column('training', 'end_time', nullable=False)

    op.drop_column('training', 'start_training_date_time')
    op.drop_column('training', 'end_training_date_time')


def downgrade() -> None:
    op.add_column('training', sa.Column('end_training_date_time', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.add_column('training', sa.Column('start_training_date_time', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))

    # Reconstruct timestamps from date + time (UTC assumed)
    op.execute("""
        UPDATE training
        SET start_training_date_time = (training_date + start_time) AT TIME ZONE 'UTC',
            end_training_date_time   = (training_date + end_time)   AT TIME ZONE 'UTC'
    """)

    op.alter_column('training', 'start_training_date_time', nullable=False)
    op.alter_column('training', 'end_training_date_time', nullable=False)

    op.drop_column('training', 'end_time')
    op.drop_column('training', 'start_time')
    op.drop_column('training', 'training_date')
