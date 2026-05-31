"""payment_system_v2

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg_enum(*values, name):
    """PostgreSQL ENUM that references an already-created type (no auto-CREATE)."""
    return PG_ENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name

    # ── Create PostgreSQL enum types (idempotent via DO block) ───────────
    if dialect == "postgresql":
        bind.execute(text("""
            DO $$ BEGIN
                CREATE TYPE entitykind AS ENUM ('USER','CLUB','POOL','SUPPLIER');
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """))
        bind.execute(text("""
            DO $$ BEGIN
                CREATE TYPE entrytype AS ENUM ('INCOME','EXPENSE');
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """))

    # ── payment_type: add new columns ────────────────────────────────────
    pt_cols = {col["name"] for col in inspector.get_columns("payment_type")}

    if "code" not in pt_cols:
        op.add_column("payment_type", sa.Column("code", sa.String(100), nullable=True))
        op.create_index("uq_payment_type_code", "payment_type", ["code"], unique=True)

    if "label" not in pt_cols:
        op.add_column("payment_type", sa.Column("label", sa.String(255), nullable=True))

    if "sender_kind" not in pt_cols:
        sender_type = _pg_enum("USER", "CLUB", "POOL", "SUPPLIER", name="entitykind") if dialect == "postgresql" else sa.String(20)
        op.add_column("payment_type", sa.Column("sender_kind", sender_type, nullable=True))

    if "receiver_kind" not in pt_cols:
        receiver_type = _pg_enum("USER", "CLUB", "POOL", "SUPPLIER", name="entitykind") if dialect == "postgresql" else sa.String(20)
        op.add_column("payment_type", sa.Column("receiver_kind", receiver_type, nullable=True))

    # Make payment_direction nullable (PostgreSQL only — SQLite skips ALTER)
    if dialect == "postgresql":
        op.alter_column("payment_type", "payment_direction", nullable=True)

    # ── wallet: add unique constraint on (owner_id, owner_type) ──────────
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("wallet")}
    if "uq_wallet_owner" not in existing_indexes:
        op.create_index("uq_wallet_owner", "wallet", ["owner_id", "owner_type"], unique=True)

    # ── payment: add description column ──────────────────────────────────
    pay_cols = {col["name"] for col in inspector.get_columns("payment")}
    if "description" not in pay_cols:
        op.add_column("payment", sa.Column("description", sa.String(500), nullable=True))

    # ── expense_category ─────────────────────────────────────────────────
    if not inspector.has_table("expense_category"):
        op.create_table(
            "expense_category",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("label", sa.String(255), nullable=False),
            sa.Column("wallet_id", sa.UUID(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["wallet_id"], ["wallet.id"]),
        )

    # ── income_category ───────────────────────────────────────────────────
    if not inspector.has_table("income_category"):
        op.create_table(
            "income_category",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("label", sa.String(255), nullable=False),
            sa.Column("wallet_id", sa.UUID(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["wallet_id"], ["wallet.id"]),
        )

    # ── income_expense ────────────────────────────────────────────────────
    if not inspector.has_table("income_expense"):
        entry_type_col = (
            _pg_enum("INCOME", "EXPENSE", name="entrytype")
            if dialect == "postgresql"
            else sa.String(10)
        )
        op.create_table(
            "income_expense",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("wallet_id", sa.UUID(), nullable=False),
            sa.Column("entry_type", entry_type_col, nullable=False),
            sa.Column("expense_category_id", sa.Integer(), nullable=True),
            sa.Column("income_category_id", sa.Integer(), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("migrated_to_payment_id", sa.UUID(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.CheckConstraint(
                "(entry_type = 'EXPENSE' AND expense_category_id IS NOT NULL AND income_category_id IS NULL)"
                " OR "
                "(entry_type = 'INCOME' AND income_category_id IS NOT NULL AND expense_category_id IS NULL)",
                name="ck_income_expense_category_matches_type",
            ),
            sa.ForeignKeyConstraint(["wallet_id"], ["wallet.id"]),
            sa.ForeignKeyConstraint(["expense_category_id"], ["expense_category.id"]),
            sa.ForeignKeyConstraint(["income_category_id"], ["income_category.id"]),
            sa.ForeignKeyConstraint(["migrated_to_payment_id"], ["payment.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_income_expense_wallet", "income_expense", ["wallet_id", "is_active"])

    # ── Data backfill: wallets for existing users / companies ─────────────
    if dialect == "postgresql":
        op.execute(text("""
            INSERT INTO wallet (id, owner_id, owner_type, created_at)
            SELECT gen_random_uuid(), u.id, 'USER'::ownertype, now()
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM wallet w WHERE w.owner_id = u.id AND w.owner_type = 'USER'::ownertype
            )
        """))
        op.execute(text("""
            INSERT INTO wallet (id, owner_id, owner_type, created_at)
            SELECT gen_random_uuid(), c.id, 'COMPANY'::ownertype, now()
            FROM company c
            WHERE NOT EXISTS (
                SELECT 1 FROM wallet w WHERE w.owner_id = c.id AND w.owner_type = 'COMPANY'::ownertype
            )
        """))
    else:
        # SQLite: uuid via hex(randomblob)
        op.execute(text("""
            INSERT INTO wallet (id, owner_id, owner_type, created_at)
            SELECT lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' ||
                   substr(lower(hex(randomblob(2))),2) || '-' ||
                   substr('89ab', abs(random()) % 4 + 1, 1) ||
                   substr(lower(hex(randomblob(2))),2) || '-' ||
                   lower(hex(randomblob(6))),
                   u.id, 'USER', datetime('now')
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM wallet w WHERE w.owner_id = u.id AND w.owner_type = 'USER'
            )
        """))
        op.execute(text("""
            INSERT INTO wallet (id, owner_id, owner_type, created_at)
            SELECT lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' ||
                   substr(lower(hex(randomblob(2))),2) || '-' ||
                   substr('89ab', abs(random()) % 4 + 1, 1) ||
                   substr(lower(hex(randomblob(2))),2) || '-' ||
                   lower(hex(randomblob(6))),
                   c.id, 'COMPANY', datetime('now')
            FROM company c
            WHERE NOT EXISTS (
                SELECT 1 FROM wallet w WHERE w.owner_id = c.id AND w.owner_type = 'COMPANY'
            )
        """))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name

    if inspector.has_table("income_expense"):
        op.drop_index("idx_income_expense_wallet", table_name="income_expense")
        op.drop_table("income_expense")

    if inspector.has_table("income_category"):
        op.drop_table("income_category")

    if inspector.has_table("expense_category"):
        op.drop_table("expense_category")

    pay_cols = {col["name"] for col in inspector.get_columns("payment")}
    if "description" in pay_cols:
        op.drop_column("payment", "description")

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("wallet")}
    if "uq_wallet_owner" in existing_indexes:
        op.drop_index("uq_wallet_owner", table_name="wallet")

    pt_indexes = {idx["name"] for idx in inspector.get_indexes("payment_type")}
    if "uq_payment_type_code" in pt_indexes:
        op.drop_index("uq_payment_type_code", table_name="payment_type")

    pt_cols = {col["name"] for col in inspector.get_columns("payment_type")}
    for col in ("receiver_kind", "sender_kind", "label", "code"):
        if col in pt_cols:
            op.drop_column("payment_type", col)

    if dialect == "postgresql":
        bind.execute(text("DROP TYPE IF EXISTS entrytype"))
        bind.execute(text("DROP TYPE IF EXISTS entitykind"))
