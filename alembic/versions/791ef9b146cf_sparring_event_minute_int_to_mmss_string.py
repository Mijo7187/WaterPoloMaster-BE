"""sparring_event minute int to mmss string

Revision ID: 791ef9b146cf
Revises: a5721e408757
Create Date: 2026-07-25 07:17:36.768423

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '791ef9b146cf'
down_revision: Union[str, None] = 'a5721e408757'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # int -> "mm:ss": Postgres has no implicit int->varchar cast for ALTER TYPE,
    # and a bare cast would produce "4" rather than a valid mm:ss string. Format
    # the existing minute count as zero-padded "mm:00" (nulls stay null).
    op.alter_column('sparring_event', 'minute',
               existing_type=sa.INTEGER(),
               type_=sa.String(length=8),
               existing_nullable=True,
               postgresql_using="lpad(minute::text, 2, '0') || ':00'")


def downgrade() -> None:
    # "mm:ss" / "hh:mm:ss" -> int: keep the leading (minutes, or hours) field.
    # Lossy by nature; text->int needs an explicit USING cast in Postgres.
    op.alter_column('sparring_event', 'minute',
               existing_type=sa.String(length=8),
               type_=sa.INTEGER(),
               existing_nullable=True,
               postgresql_using="split_part(minute, ':', 1)::integer")
