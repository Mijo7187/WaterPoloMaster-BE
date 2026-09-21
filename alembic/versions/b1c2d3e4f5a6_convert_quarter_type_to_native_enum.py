"""convert_quarter_type_to_native_enum

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-07-04 00:05:00.000000

Converts quarter.quarter_type from VARCHAR(2) to a native Postgres ENUM
('quartertype') so it matches the SQLAlchemy model's Enum(QuarterType).
Existing values ('Q1'..'Q4') already match the enum labels, so the cast is
lossless.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    quartertype = postgresql.ENUM('Q1', 'Q2', 'Q3', 'Q4', name='quartertype')
    quartertype.create(op.get_bind(), checkfirst=True)

    op.alter_column(
        'quarter', 'quarter_type',
        existing_type=sa.VARCHAR(length=2),
        type_=postgresql.ENUM('Q1', 'Q2', 'Q3', 'Q4', name='quartertype', create_type=False),
        existing_nullable=False,
        postgresql_using='quarter_type::quartertype',
    )


def downgrade() -> None:
    op.alter_column(
        'quarter', 'quarter_type',
        existing_type=postgresql.ENUM('Q1', 'Q2', 'Q3', 'Q4', name='quartertype', create_type=False),
        type_=sa.String(length=2),
        existing_nullable=False,
        postgresql_using='quarter_type::text',
    )
    postgresql.ENUM(name='quartertype').drop(op.get_bind(), checkfirst=True)
