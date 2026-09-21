"""add_context_ids_to_payment

Revision ID: c8d9e0f1a2b3
Revises: b1c2d3e4f5a6
Create Date: 2026-07-04 18:30:00.000000

Adds nullable, indexed FK columns quarter_id / tournament_id / training_id to
`payment` so payments can be filtered/paginated by their business context
without parsing the free-text `description`.

DATA BACKFILL
-------------
The payment_type.code enum tells you which context each payment *should* carry:
    USER_QUARTERLY_FEE                        -> quarter_id
    USER_TOURNAMENT_FEE, CLUB_TOURNAMENT_POOL -> tournament_id
    CLUB_TRAINING_POOL                        -> training_id
    CLUB_SALARY_USER                          -> none

CLUB_TRAINING_POOL payments are the only kind ever generated so far
(app/scheduler/training_jobs.py). Each is created from a Training with the exact
tuple (sender=club wallet, receiver=pool wallet, amount=training.price,
description="Training payment for {training_date}"). We reverse that tuple to
recover training_id deterministically. When several identical trainings share
the same (club, pool, price, date) we pair the Nth such payment with the Nth
such training (row_number), giving a clean 1:1 mapping. The UPDATE is idempotent
(only touches rows where training_id IS NULL).

No USER_QUARTERLY_FEE / *_TOURNAMENT_* payments exist yet and no code path emits
them, so quarter_id / tournament_id backfill is left as a documented skeleton
(see _backfill_quarter_tournament) to be filled in deliberately if such history
ever appears.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Description prefix the scheduler writes for training-pool payments.
_TRAINING_DESC_PREFIX = "Training payment for "


def _backfill_training_pool(bind) -> None:
    """Recover training_id for CLUB_TRAINING_POOL payments from their originating
    Training. Deterministic, 1:1 within identical groups, idempotent."""
    bind.execute(
        sa.text(
            """
            WITH pay_ranked AS (
                SELECT
                    p.id AS pay_id,
                    club.id AS company_id,
                    pool.id AS pool_id,
                    p.amount AS amount,
                    (substring(p.description FROM :desc_re))::date AS tdate,
                    row_number() OVER (
                        PARTITION BY club.id, pool.id, p.amount, p.description
                        ORDER BY p.created_at, p.id
                    ) AS rn
                FROM payment p
                JOIN payment_type pt ON pt.id = p.payment_type_id
                JOIN company club ON club.w_id = p.sender_wallet_id
                JOIN company pool ON pool.w_id = p.receiver_wallet_id
                WHERE pt.code = 'CLUB_TRAINING_POOL'
                  AND p.training_id IS NULL
                  AND p.description LIKE :desc_like
            ),
            train_ranked AS (
                SELECT
                    t.id AS training_id,
                    t.company_id, t.pool_id, t.price, t.training_date,
                    row_number() OVER (
                        PARTITION BY t.company_id, t.pool_id, t.price, t.training_date
                        ORDER BY t.id
                    ) AS rn
                FROM training t
            )
            UPDATE payment p
            SET training_id = tr.training_id
            FROM pay_ranked pr
            JOIN train_ranked tr
              ON tr.company_id = pr.company_id
             AND tr.pool_id = pr.pool_id
             AND tr.price = pr.amount
             AND tr.training_date = pr.tdate
             AND tr.rn = pr.rn
            WHERE p.id = pr.pay_id
            """
        ),
        {
            "desc_re": _TRAINING_DESC_PREFIX + "(.*)$",
            "desc_like": _TRAINING_DESC_PREFIX + "%",
        },
    )


def _backfill_quarter_tournament(bind) -> None:
    """No such payments exist yet and nothing generates them. Left as a
    deliberate skeleton — fill in only after confirming a real linkage.

    # USER_QUARTERLY_FEE -> quarter_id
    # bind.execute(sa.text(
    #     "UPDATE payment AS p SET quarter_id = q.id "
    #     "FROM quarter AS q, payment_type AS pt "
    #     "WHERE p.payment_type_id = pt.id AND pt.code = 'USER_QUARTERLY_FEE' "
    #     "  AND <verified linkage between p and q>"
    # ))
    #
    # USER_TOURNAMENT_FEE / CLUB_TOURNAMENT_POOL -> tournament_id
    # bind.execute(sa.text(
    #     "UPDATE payment AS p SET tournament_id = t.id "
    #     "FROM tournament AS t, payment_type AS pt "
    #     "WHERE p.payment_type_id = pt.id "
    #     "  AND pt.code IN ('USER_TOURNAMENT_FEE', 'CLUB_TOURNAMENT_POOL') "
    #     "  AND <verified linkage between p and t>"
    # ))
    """


def upgrade() -> None:
    # 1. Add the columns as nullable so existing rows survive.
    op.add_column('payment', sa.Column('quarter_id', sa.Integer(), nullable=True))
    op.add_column('payment', sa.Column('tournament_id', sa.Integer(), nullable=True))
    op.add_column('payment', sa.Column('training_id', sa.Integer(), nullable=True))

    # 2. Foreign keys to the business entities.
    op.create_foreign_key(
        'fk_payment_quarter_id', 'payment', 'quarter', ['quarter_id'], ['id']
    )
    op.create_foreign_key(
        'fk_payment_tournament_id', 'payment', 'tournament', ['tournament_id'], ['id']
    )
    op.create_foreign_key(
        'fk_payment_training_id', 'payment', 'training', ['training_id'], ['id']
    )

    # 3. Indexes for fast filtering/pagination by context.
    op.create_index('ix_payment_quarter_id', 'payment', ['quarter_id'])
    op.create_index('ix_payment_tournament_id', 'payment', ['tournament_id'])
    op.create_index('ix_payment_training_id', 'payment', ['training_id'])

    # 4. Data backfill for existing history.
    bind = op.get_bind()
    _backfill_training_pool(bind)
    _backfill_quarter_tournament(bind)  # skeleton — no such payments exist yet


def downgrade() -> None:
    op.drop_index('ix_payment_training_id', table_name='payment')
    op.drop_index('ix_payment_tournament_id', table_name='payment')
    op.drop_index('ix_payment_quarter_id', table_name='payment')

    op.drop_constraint('fk_payment_training_id', 'payment', type_='foreignkey')
    op.drop_constraint('fk_payment_tournament_id', 'payment', type_='foreignkey')
    op.drop_constraint('fk_payment_quarter_id', 'payment', type_='foreignkey')

    op.drop_column('payment', 'training_id')
    op.drop_column('payment', 'tournament_id')
    op.drop_column('payment', 'quarter_id')
