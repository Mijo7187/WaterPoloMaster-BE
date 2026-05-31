"""remove_pool_table

Revision ID: 6965b30123fb
Revises: 8d9961a665ab
Create Date: 2026-04-03 13:55:52.754731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6965b30123fb'
down_revision: Union[str, None] = '8d9961a665ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop FK from training to pool, then drop pool_id column
    op.drop_constraint("training_pool_id_fkey", "training", type_="foreignkey")
    op.drop_column("training", "pool_id")
    # Drop FKs from pool to city/country, drop index, then drop pool table
    op.drop_constraint("pool_city_id_fkey", "pool", type_="foreignkey")
    op.drop_constraint("pool_country_id_fkey", "pool", type_="foreignkey")
    op.drop_index(op.f("ix_pool_id"), table_name="pool")
    op.drop_table("pool")


def downgrade() -> None:
    op.create_table(
        "pool",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("address_number", sa.String(length=50), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("city_id", sa.Integer(), nullable=True),
        sa.Column("country_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["city_id"], ["city.id"], name="pool_city_id_fkey"),
        sa.ForeignKeyConstraint(["country_id"], ["country.id"], name="pool_country_id_fkey"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pool_id"), "pool", ["id"], unique=False)
    op.add_column("training", sa.Column("pool_id", sa.Integer(), nullable=True))
    op.create_foreign_key("training_pool_id_fkey", "training", "pool", ["pool_id"], ["id"])
