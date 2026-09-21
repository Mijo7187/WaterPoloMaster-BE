"""sparring team side + participant roster

Revision ID: 4e7cf07610c9
Revises: 36d221b51459
Create Date: 2026-07-19 13:37:21.636391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4e7cf07610c9'
down_revision: Union[str, None] = '36d221b51459'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Shared enum object with create_type=False so column DDL never emits CREATE TYPE;
# the type is created/dropped exactly once, explicitly, with checkfirst.
sparringside = postgresql.ENUM('HOME', 'AWAY', name='sparringside', create_type=False)


def upgrade() -> None:
    # Autogenerate missed sparring_participant (already present in the dev DB via
    # create_all); added by hand below so migrations remain authoritative.
    sparringside.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'sparring_participant',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('segment_sparring_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('side', sparringside, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['segment_sparring_id'], ['segment_sparring.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('segment_sparring_id', 'user_id'),
    )
    op.create_index(op.f('ix_sparring_participant_id'), 'sparring_participant', ['id'])
    op.create_index(
        op.f('ix_sparring_participant_segment_sparring_id'),
        'sparring_participant', ['segment_sparring_id'],
    )

    op.add_column('sparring_event', sa.Column('side', sparringside, nullable=True))
    op.alter_column('sparring_event', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade() -> None:
    op.alter_column('sparring_event', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_column('sparring_event', 'side')
    op.drop_index(op.f('ix_sparring_participant_segment_sparring_id'), 'sparring_participant')
    op.drop_index(op.f('ix_sparring_participant_id'), 'sparring_participant')
    op.drop_table('sparring_participant')
    sparringside.drop(op.get_bind(), checkfirst=True)
