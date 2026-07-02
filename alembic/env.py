from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ── Project imports ──────────────────────────────────────────
from app.core.config import settings
from app.core.db.base import Base

# Import ALL models here so Alembic can detect them for autogenerate
from app.features.users.users_models import User  # noqa: F401
from app.features.sifarnici.country.country_model import Country  # noqa: F401
from app.features.sifarnici.city.city_model import City  # noqa: F401
from app.features.company.company_model import Company  # noqa: F401
from app.features.training.training_model import Training  # noqa: F401
from app.features.wallet.wallet_model import Wallet  # noqa: F401
from app.features.sifarnici.payment_type.payment_type_model import PaymentType  # noqa: F401
from app.features.payment.payment_model import Payment  # noqa: F401
from app.features.sifarnici.expense_category.expense_category_model import ExpenseCategory  # noqa: F401
from app.features.sifarnici.income_category.income_category_model import IncomeCategory  # noqa: F401
from app.features.sifarnici.training_type.training_type_model import TrainingType  # noqa: F401
from app.features.sifarnici.swimming_discipline.swimming_discipline_model import SwimmingDiscipline  # noqa: F401
from app.features.training_users_list.training_users_list_model import TrainingUsersList  # noqa: F401
from app.features.quarter.quarter_model import Quarter  # noqa: F401
from app.features.quarter_users.quarter_users_model import QuarterUsers  # noqa: F401
from app.features.tournament.tournament_model import Tournament  # noqa: F401
from app.features.tournament_users.tournament_users_model import TournamentUsers  # noqa: F401

# ─────────────────────────────────────────────────────────────

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic at our models' metadata for autogenerate support
target_metadata = Base.metadata

# Override sqlalchemy.url with the value from our .env file
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
