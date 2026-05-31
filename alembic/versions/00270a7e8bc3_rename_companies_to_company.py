"""rename_companies_to_company

Revision ID: 00270a7e8bc3
Revises: 981cc883217a
Create Date: 2026-03-28 23:52:10.391000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00270a7e8bc3'
down_revision: Union[str, None] = '981cc883217a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the empty company table that create_tables() auto-created from the updated model
    op.drop_table("company")

    # Drop FKs referencing companies before renaming
    op.drop_constraint("training_company_id_fkey", "training", type_="foreignkey")
    op.drop_constraint("users_company_id_fkey", "users", type_="foreignkey")

    op.rename_table("companies", "company")

    # Re-create FKs pointing to the new table name
    op.create_foreign_key("training_company_id_fkey", "training", "company", ["company_id"], ["id"])
    op.create_foreign_key("users_company_id_fkey", "users", "company", ["company_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("training_company_id_fkey", "training", type_="foreignkey")
    op.drop_constraint("users_company_id_fkey", "users", type_="foreignkey")

    op.rename_table("company", "companies")

    op.create_foreign_key("training_company_id_fkey", "training", "companies", ["company_id"], ["id"])
    op.create_foreign_key("users_company_id_fkey", "users", "companies", ["company_id"], ["id"])
    pass
