"""payment_type enum rework

Revision ID: 9989f889b9ad
Revises: c3d4e5f6a7b8
Create Date: 2026-05-30 18:42:23.922077

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision: str = "9989f889b9ad"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PAYMENT_TYPE_CODES = (
    "USER_QUARTERLY_FEE",
    "USER_TOURNAMENT_FEE",
    "CLUB_TOURNAMENT_POOL",
    "CLUB_SALARY_USER",
    "CLUB_TRAINING_POOL",
)

WALLET_OWNER_TYPES = ("USER", "COMPANY")

SEED_ROWS = [
    ("User Quarterly Fee",  "USER_QUARTERLY_FEE",   "USER",    "COMPANY"),
    ("User Tournament Fee", "USER_TOURNAMENT_FEE",  "USER",    "COMPANY"),
    ("Club Tournament Pool","CLUB_TOURNAMENT_POOL", "COMPANY", "COMPANY"),
    ("Club Salary User",    "CLUB_SALARY_USER",     "COMPANY", "USER"),
    ("Club Training Pool",  "CLUB_TRAINING_POOL",   "COMPANY", "COMPANY"),
]


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Drop dependent table first ────────────────────────────
    op.drop_table("income_expense")

    # ── 2. Wipe rows whose shape changes incompatibly ────────────
    #     Payments reference payment_type by FK; clear them too.
    bind.execute(text("DELETE FROM payment"))
    bind.execute(text("DELETE FROM payment_type"))

    # ── 3. Create new enum types up front (idempotent) ───────────
    bind.execute(text("""
        DO $$ BEGIN
            CREATE TYPE walletownertype AS ENUM ('USER','COMPANY');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    bind.execute(text("""
        DO $$ BEGIN
            CREATE TYPE paymenttypecode AS ENUM (
                'USER_QUARTERLY_FEE','USER_TOURNAMENT_FEE','CLUB_TOURNAMENT_POOL',
                'CLUB_SALARY_USER','CLUB_TRAINING_POOL'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))

    # ── 4. payment_type: drop legacy columns ─────────────────────
    op.drop_index("uq_payment_type_code", table_name="payment_type")
    op.drop_column("payment_type", "label")
    op.drop_column("payment_type", "description")
    op.drop_column("payment_type", "payment_direction")
    op.drop_column("payment_type", "receiver_kind")
    op.drop_column("payment_type", "sender_kind")

    # ── 5. payment_type.id : UUID → Integer (table is empty) ─────
    #     First drop dependent FK from payment.
    op.execute(
        "ALTER TABLE payment DROP CONSTRAINT IF EXISTS payment_payment_type_id_fkey"
    )
    op.execute(
        "ALTER TABLE payment_type DROP CONSTRAINT IF EXISTS payment_type_pkey"
    )
    op.drop_column("payment_type", "id")
    op.add_column(
        "payment_type",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
    )
    op.create_primary_key("payment_type_pkey", "payment_type", ["id"])
    op.create_index(op.f("ix_payment_type_id"), "payment_type", ["id"], unique=False)

    # ── 6. payment_type.code : VARCHAR → enum ────────────────────
    op.execute(
        "ALTER TABLE payment_type "
        "ALTER COLUMN code TYPE paymenttypecode USING code::paymenttypecode, "
        "ALTER COLUMN code SET NOT NULL"
    )

    # ── 7. payment_type: add new sender/receiver enum columns ────
    op.add_column(
        "payment_type",
        sa.Column(
            "sender_type",
            postgresql.ENUM("USER", "COMPANY", name="walletownertype", create_type=False),
            nullable=False,
        ),
    )
    op.add_column(
        "payment_type",
        sa.Column(
            "receiver_type",
            postgresql.ENUM("USER", "COMPANY", name="walletownertype", create_type=False),
            nullable=False,
        ),
    )

    # ── 8. payment.payment_type_id : UUID → Integer (table empty) ─
    op.execute(
        "ALTER TABLE payment ALTER COLUMN payment_type_id TYPE integer "
        "USING NULL"
    )
    # NULL above is fine because payment table is empty; but we need a real FK target.
    # Re-establish FK now (autogen detected it as already-present, but cast may have dropped it).
    bind.execute(text("""
        ALTER TABLE payment
        DROP CONSTRAINT IF EXISTS payment_payment_type_id_fkey
    """))
    op.create_foreign_key(
        "payment_payment_type_id_fkey",
        "payment",
        "payment_type",
        ["payment_type_id"],
        ["id"],
    )

    # ── 9. wallet.owner_type : ownertype → walletownertype ───────
    op.execute(
        "ALTER TABLE wallet "
        "ALTER COLUMN owner_type TYPE walletownertype "
        "USING owner_type::text::walletownertype"
    )

    # ── 10. wallet unique constraint: index → real constraint ────
    op.drop_index("uq_wallet_owner", table_name="wallet")
    op.create_unique_constraint("uq_wallet_owner", "wallet", ["owner_id", "owner_type"])

    # ── 11. Drop legacy enum types now that nothing references them
    bind.execute(text("DROP TYPE IF EXISTS ownertype"))
    bind.execute(text("DROP TYPE IF EXISTS entitykind"))
    bind.execute(text("DROP TYPE IF EXISTS entrytype"))
    bind.execute(text("DROP TYPE IF EXISTS paymentdirection"))

    # ── 12. Seed the 5 PaymentType rows ──────────────────────────
    for name, code, sender_type, receiver_type in SEED_ROWS:
        bind.execute(
            text(
                "INSERT INTO payment_type (name, code, sender_type, receiver_type, active, created_at) "
                "VALUES (:name, CAST(:code AS paymenttypecode), "
                "CAST(:sender AS walletownertype), CAST(:receiver AS walletownertype), "
                "true, now())"
            ),
            {"name": name, "code": code, "sender": sender_type, "receiver": receiver_type},
        )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(text("DELETE FROM payment"))
    bind.execute(text("DELETE FROM payment_type"))

    # Recreate legacy enums
    bind.execute(text(
        "CREATE TYPE ownertype AS ENUM ('USER','COMPANY')"
    ))
    bind.execute(text(
        "CREATE TYPE entitykind AS ENUM ('USER','CLUB','POOL','SUPPLIER')"
    ))
    bind.execute(text(
        "CREATE TYPE paymentdirection AS ENUM ('C_C','U_C','C_U')"
    ))
    bind.execute(text(
        "CREATE TYPE entrytype AS ENUM ('INCOME','EXPENSE')"
    ))

    # Revert wallet.owner_type
    op.drop_constraint("uq_wallet_owner", "wallet", type_="unique")
    op.execute(
        "ALTER TABLE wallet "
        "ALTER COLUMN owner_type TYPE ownertype "
        "USING owner_type::text::ownertype"
    )
    op.create_index("uq_wallet_owner", "wallet", ["owner_id", "owner_type"], unique=True)

    # Revert payment.payment_type_id  Integer → UUID
    op.execute(
        "ALTER TABLE payment ALTER COLUMN payment_type_id TYPE uuid USING NULL"
    )

    # payment_type rollback
    op.drop_column("payment_type", "receiver_type")
    op.drop_column("payment_type", "sender_type")
    op.execute(
        "ALTER TABLE payment_type ALTER COLUMN code TYPE varchar(100) USING code::text, "
        "ALTER COLUMN code DROP NOT NULL"
    )
    op.drop_index(op.f("ix_payment_type_id"), table_name="payment_type")
    op.execute("ALTER TABLE payment_type DROP CONSTRAINT IF EXISTS payment_type_pkey")
    op.drop_column("payment_type", "id")
    op.add_column(
        "payment_type",
        sa.Column("id", sa.UUID(), nullable=False),
    )
    op.create_primary_key("payment_type_pkey", "payment_type", ["id"])
    op.create_index("uq_payment_type_code", "payment_type", ["code"], unique=True)

    op.add_column(
        "payment_type",
        sa.Column("sender_kind", postgresql.ENUM(name="entitykind", create_type=False), nullable=True),
    )
    op.add_column(
        "payment_type",
        sa.Column("receiver_kind", postgresql.ENUM(name="entitykind", create_type=False), nullable=True),
    )
    op.add_column(
        "payment_type",
        sa.Column("payment_direction", postgresql.ENUM(name="paymentdirection", create_type=False), nullable=True),
    )
    op.add_column("payment_type", sa.Column("description", sa.TEXT(), nullable=True))
    op.add_column("payment_type", sa.Column("label", sa.VARCHAR(length=255), nullable=True))

    bind.execute(text("DROP TYPE IF EXISTS paymenttypecode"))
    bind.execute(text("DROP TYPE IF EXISTS walletownertype"))

    # Recreate income_expense table
    op.create_table(
        "income_expense",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("wallet_id", sa.UUID(), nullable=False),
        sa.Column("entry_type", postgresql.ENUM(name="entrytype", create_type=False), nullable=False),
        sa.Column("expense_category_id", sa.INTEGER(), nullable=True),
        sa.Column("income_category_id", sa.INTEGER(), nullable=True),
        sa.Column("amount", sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column("description", sa.VARCHAR(length=500), nullable=False),
        sa.Column("occurred_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("migrated_to_payment_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.BOOLEAN(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["expense_category_id"], ["expense_category.id"]),
        sa.ForeignKeyConstraint(["income_category_id"], ["income_category.id"]),
        sa.ForeignKeyConstraint(["migrated_to_payment_id"], ["payment.id"]),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallet.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
