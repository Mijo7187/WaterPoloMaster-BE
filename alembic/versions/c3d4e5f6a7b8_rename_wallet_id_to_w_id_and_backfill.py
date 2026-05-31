"""rename_wallet_id_to_w_id_and_backfill

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name

    users_cols = {col["name"] for col in inspector.get_columns("users")}
    company_cols = {col["name"] for col in inspector.get_columns("company")}

    # ── Rename wallet_id → w_id in users ────────────────────────────────
    if "wallet_id" in users_cols and "w_id" not in users_cols:
        if dialect == "postgresql":
            try:
                op.drop_constraint("fk_users_wallet_id", "users", type_="foreignkey")
            except Exception:
                pass
            op.alter_column("users", "wallet_id", new_column_name="w_id")
            op.create_foreign_key("fk_users_w_id", "users", "wallet", ["w_id"], ["id"])
        else:
            with op.batch_alter_table("users", recreate="always") as batch_op:
                batch_op.alter_column("wallet_id", new_column_name="w_id")
    elif "w_id" not in users_cols:
        op.add_column("users", sa.Column("w_id", sa.UUID(), nullable=True))
        if dialect == "postgresql":
            op.create_foreign_key("fk_users_w_id", "users", "wallet", ["w_id"], ["id"])

    # ── Rename wallet_id → w_id in company ──────────────────────────────
    if "wallet_id" in company_cols and "w_id" not in company_cols:
        if dialect == "postgresql":
            try:
                op.drop_constraint("fk_company_wallet_id", "company", type_="foreignkey")
            except Exception:
                pass
            op.alter_column("company", "wallet_id", new_column_name="w_id")
            op.create_foreign_key("fk_company_w_id", "company", "wallet", ["w_id"], ["id"])
        else:
            with op.batch_alter_table("company", recreate="always") as batch_op:
                batch_op.alter_column("wallet_id", new_column_name="w_id")
    elif "w_id" not in company_cols:
        op.add_column("company", sa.Column("w_id", sa.UUID(), nullable=True))
        if dialect == "postgresql":
            op.create_foreign_key("fk_company_w_id", "company", "wallet", ["w_id"], ["id"])

    # ── Backfill w_id from wallet table ─────────────────────────────────
    if dialect == "postgresql":
        bind.execute(text("""
            UPDATE users u
            SET w_id = w.id
            FROM wallet w
            WHERE w.owner_id = u.id
              AND w.owner_type = 'USER'::ownertype
              AND u.w_id IS NULL
        """))
        bind.execute(text("""
            UPDATE company c
            SET w_id = w.id
            FROM wallet w
            WHERE w.owner_id = c.id
              AND w.owner_type = 'COMPANY'::ownertype
              AND c.w_id IS NULL
        """))
    else:
        bind.execute(text("""
            UPDATE users
            SET w_id = (
                SELECT id FROM wallet
                WHERE owner_id = users.id AND owner_type = 'USER'
            )
            WHERE w_id IS NULL
        """))
        bind.execute(text("""
            UPDATE company
            SET w_id = (
                SELECT id FROM wallet
                WHERE owner_id = company.id AND owner_type = 'COMPANY'
            )
            WHERE w_id IS NULL
        """))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name

    users_cols = {col["name"] for col in inspector.get_columns("users")}
    company_cols = {col["name"] for col in inspector.get_columns("company")}

    if "w_id" in users_cols and "wallet_id" not in users_cols:
        if dialect == "postgresql":
            try:
                op.drop_constraint("fk_users_w_id", "users", type_="foreignkey")
            except Exception:
                pass
            op.alter_column("users", "w_id", new_column_name="wallet_id")
            op.create_foreign_key("fk_users_wallet_id", "users", "wallet", ["wallet_id"], ["id"])
        else:
            with op.batch_alter_table("users", recreate="always") as batch_op:
                batch_op.alter_column("w_id", new_column_name="wallet_id")

    if "w_id" in company_cols and "wallet_id" not in company_cols:
        if dialect == "postgresql":
            try:
                op.drop_constraint("fk_company_w_id", "company", type_="foreignkey")
            except Exception:
                pass
            op.alter_column("company", "w_id", new_column_name="wallet_id")
            op.create_foreign_key("fk_company_wallet_id", "company", "wallet", ["wallet_id"], ["id"])
        else:
            with op.batch_alter_table("company", recreate="always") as batch_op:
                batch_op.alter_column("w_id", new_column_name="wallet_id")
