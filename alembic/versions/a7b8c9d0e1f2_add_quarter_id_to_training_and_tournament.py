"""add_quarter_id_to_training_and_tournament

Revision ID: a7b8c9d0e1f2
Revises: 53b128a2a0e5
Create Date: 2026-07-04 00:00:00.000000

Adds a quarter_id FK to `training` and `tournament`, then backfills every
existing row with the quarter matching its date (training_date / from_date):
month -> Q1..Q4, scoped by the row's company_id + year. Any quarter that does
not yet exist is created with default prices (waterpolo 15000, swimming 6000).
Finally the column is made NOT NULL.
"""
from typing import Sequence, Union
from datetime import date

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = '53b128a2a0e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_WATERPOLO_PRICE = 15000
DEFAULT_SWIMMING_PRICE = 6000


def _quarter_type_for_month(month: int) -> str:
    return {
        1: "Q1", 2: "Q1", 3: "Q1",
        4: "Q2", 5: "Q2", 6: "Q2",
        7: "Q3", 8: "Q3", 9: "Q3",
        10: "Q4", 11: "Q4", 12: "Q4",
    }[month]


def _backfill(bind, table: str, date_column: str) -> None:
    """Resolve (creating if needed) a quarter for every row and set quarter_id."""
    # cache of (company_id, quarter_type, year) -> quarter id created/seen in this run
    quarter_cache: dict = {}

    rows = bind.execute(
        sa.text(f"SELECT id, company_id, {date_column} AS d FROM {table}")
    ).fetchall()

    for row in rows:
        d: date = row.d
        qtype = _quarter_type_for_month(d.month)
        year = d.year
        key = (row.company_id, qtype, year)

        quarter_id = quarter_cache.get(key)
        if quarter_id is None:
            found = bind.execute(
                sa.text(
                    "SELECT id FROM quarter "
                    "WHERE company_id = :cid AND quarter_type = :qt AND year = :yr"
                ),
                {"cid": row.company_id, "qt": qtype, "yr": year},
            ).fetchone()

            if found is not None:
                quarter_id = found.id
            else:
                quarter_id = bind.execute(
                    sa.text(
                        "INSERT INTO quarter "
                        "(quarter_type, year, waterpolo_price, swimming_price, "
                        " description, company_id) "
                        "VALUES (:qt, :yr, :wp, :sp, NULL, :cid) "
                        "RETURNING id"
                    ),
                    {
                        "qt": qtype,
                        "yr": year,
                        "wp": DEFAULT_WATERPOLO_PRICE,
                        "sp": DEFAULT_SWIMMING_PRICE,
                        "cid": row.company_id,
                    },
                ).scalar_one()

            quarter_cache[key] = quarter_id

        bind.execute(
            sa.text(f"UPDATE {table} SET quarter_id = :qid WHERE id = :id"),
            {"qid": quarter_id, "id": row.id},
        )


def upgrade() -> None:
    # 1. Add the column as nullable + FK so existing rows survive.
    op.add_column('training', sa.Column('quarter_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_training_quarter_id', 'training', 'quarter', ['quarter_id'], ['id']
    )
    op.add_column('tournament', sa.Column('quarter_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_tournament_quarter_id', 'tournament', 'quarter', ['quarter_id'], ['id']
    )

    # 2. Backfill every existing row (creating missing quarters with defaults).
    bind = op.get_bind()
    _backfill(bind, 'training', 'training_date')
    _backfill(bind, 'tournament', 'from_date')

    # 3. Enforce NOT NULL now that every row has a quarter.
    op.alter_column('training', 'quarter_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('tournament', 'quarter_id', existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    # Drop the columns/FKs; leave any auto-created quarters in place.
    op.drop_constraint('fk_tournament_quarter_id', 'tournament', type_='foreignkey')
    op.drop_column('tournament', 'quarter_id')
    op.drop_constraint('fk_training_quarter_id', 'training', type_='foreignkey')
    op.drop_column('training', 'quarter_id')
