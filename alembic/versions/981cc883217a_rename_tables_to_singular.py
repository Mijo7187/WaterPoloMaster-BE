"""rename_tables_to_singular

Revision ID: 981cc883217a
Revises: f711e4cfdd38
Create Date: 2026-03-28 23:45:26.486012

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '981cc883217a'
down_revision: Union[str, None] = 'f711e4cfdd38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Step 1: Drop new empty tables that create_tables() created ──────────
    # (they were auto-created from the updated models before this migration runs)
    # Drop in FK dependency order

    # training has FKs to pool and companies
    op.drop_constraint("training_pool_id_fkey", "training", type_="foreignkey")
    op.drop_constraint("training_company_id_fkey", "training", type_="foreignkey")
    op.drop_table("training")

    # pool has FKs to city and country
    op.drop_constraint("pool_city_id_fkey", "pool", type_="foreignkey")
    op.drop_constraint("pool_country_id_fkey", "pool", type_="foreignkey")
    op.drop_table("pool")

    # city has FK to country
    op.drop_constraint("city_country_id_fkey", "city", type_="foreignkey")
    op.drop_table("city")

    op.drop_table("country")

    # ── Step 2: Drop FKs on old tables so we can rename freely ──────────────
    op.drop_constraint("pools_city_id_fkey", "pools", type_="foreignkey")
    op.drop_constraint("pools_country_id_fkey", "pools", type_="foreignkey")
    op.drop_constraint("cities_country_id_fkey", "cities", type_="foreignkey")
    op.drop_constraint("trenings_pool_id_fkey", "trainings", type_="foreignkey")
    op.drop_constraint("fk_trainings_company_id", "trainings", type_="foreignkey")
    op.drop_constraint("trening_users_trening_id_fkey", "training_users", type_="foreignkey")

    # ── Step 3: Rename tables ────────────────────────────────────────────────
    op.rename_table("countries", "country")
    op.rename_table("cities", "city")
    op.rename_table("pools", "pool")
    op.rename_table("trainings", "training")

    # ── Step 4: Re-create FKs with correct singular table names ─────────────
    op.create_foreign_key("city_country_id_fkey", "city", "country", ["country_id"], ["id"])
    op.create_foreign_key("pool_city_id_fkey", "pool", "city", ["city_id"], ["id"])
    op.create_foreign_key("pool_country_id_fkey", "pool", "country", ["country_id"], ["id"])
    op.create_foreign_key("training_pool_id_fkey", "training", "pool", ["pool_id"], ["id"])
    op.create_foreign_key("training_company_id_fkey", "training", "companies", ["company_id"], ["id"])
    op.create_foreign_key("trening_users_trening_id_fkey", "training_users", "training", ["training_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("trening_users_trening_id_fkey", "training_users", type_="foreignkey")
    op.drop_constraint("training_company_id_fkey", "training", type_="foreignkey")
    op.drop_constraint("training_pool_id_fkey", "training", type_="foreignkey")
    op.drop_constraint("pool_country_id_fkey", "pool", type_="foreignkey")
    op.drop_constraint("pool_city_id_fkey", "pool", type_="foreignkey")
    op.drop_constraint("city_country_id_fkey", "city", type_="foreignkey")

    op.rename_table("training", "trainings")
    op.rename_table("pool", "pools")
    op.rename_table("city", "cities")
    op.rename_table("country", "countries")

    op.create_foreign_key("trening_users_trening_id_fkey", "training_users", "trainings", ["training_id"], ["id"])
    op.create_foreign_key("fk_trainings_company_id", "trainings", "companies", ["company_id"], ["id"])
    op.create_foreign_key("trenings_pool_id_fkey", "trainings", "pools", ["pool_id"], ["id"])
    op.create_foreign_key("cities_country_id_fkey", "cities", "countries", ["country_id"], ["id"])
    op.create_foreign_key("pools_country_id_fkey", "pools", "countries", ["country_id"], ["id"])
    op.create_foreign_key("pools_city_id_fkey", "pools", "cities", ["city_id"], ["id"])
