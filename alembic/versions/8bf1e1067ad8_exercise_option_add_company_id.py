"""exercise_option: add company_id

Revision ID: 8bf1e1067ad8
Revises: 874bdb0952e7
Create Date: 2026-09-09

Pre-existing drift, unrelated to the membership change that precedes it:
exercise_option_model declares company_id (an FK, NOT NULL) and scopes its
uniqueness on (company_id, segment_type, code), but no migration ever added
the column — the dev DB only has the older UNIQUE(segment_type, code).

The column is added NOT NULL with no backfill, which is safe only while the
table is empty. It is a young per-company sifarnik and is empty in dev; if any
environment already holds rows, this will fail loudly rather than inventing a
company for them — backfill there first, then re-run.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8bf1e1067ad8'
down_revision: Union[str, None] = '874bdb0952e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("exercise_option", sa.Column("company_id", sa.Integer(), nullable=False))
    op.create_foreign_key(
        "exercise_option_company_id_fkey", "exercise_option", "company",
        ["company_id"], ["id"],
    )
    op.drop_constraint(
        "exercise_option_segment_type_code_key", "exercise_option", type_="unique"
    )
    op.create_unique_constraint(
        "uq_exercise_option_company_segment_code",
        "exercise_option",
        ["company_id", "segment_type", "code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_exercise_option_company_segment_code", "exercise_option", type_="unique"
    )
    op.create_unique_constraint(
        "exercise_option_segment_type_code_key",
        "exercise_option",
        ["segment_type", "code"],
    )
    op.drop_constraint(
        "exercise_option_company_id_fkey", "exercise_option", type_="foreignkey"
    )
    op.drop_column("exercise_option", "company_id")
