"""
Clear the dev database's transactional data — rows only, never the tables.

Truncates the billing chain, the training/tournament data and the season, then
restarts their identity sequences so new rows start at 1 again:

  * payment, contract_installment, contract
  * group_user, group, membership
  * season
  * training, training_users, training_segment
  * segment_exercise, segment_sparring, sparring_participant, sparring_event
  * tournament, tournament_users

Deliberately KEPT, so you stay logged in and keep your reference data:

  * users, company, wallet
  * country, city, selection, exercise_option, income_category, expense_category

Why wallet is kept: users.w_id and company.w_id point AT wallet, so users and
company are the children of that foreign key. Truncating wallet with CASCADE
would therefore empty users and company too, and from company it would cascade
on into selection and exercise_option. Nothing is lost by keeping it — wallet
has no balance column, balances are derived from the payment ledger, so
truncating payment already zeroes every balance.

The schema, the indexes, the enums and alembic_version are all untouched; this
script never drops or alters anything. Afterwards re-seed with
seed_base_data.py (minimal) or seed_dev_data.py (full billing dataset).

Run with: python reset_dev_data.py        (asks for confirmation)
          python reset_dev_data.py --yes  (skips the prompt)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import every model so the SQLAlchemy mapper can resolve all relationships.
import app.features.users.users_models  # noqa: F401,E402
import app.features.company.company_model  # noqa: F401,E402
import app.features.sifarnici.country.country_model  # noqa: F401,E402
import app.features.sifarnici.city.city_model  # noqa: F401,E402
import app.features.sifarnici.exercise_option.exercise_option_model  # noqa: F401,E402
import app.features.sifarnici.expense_category.expense_category_model  # noqa: F401,E402
import app.features.sifarnici.income_category.income_category_model  # noqa: F401,E402
import app.features.sifarnici.selection.selection_model  # noqa: F401,E402
import app.features.group.group_model  # noqa: F401,E402
import app.features.group_user.group_user_model  # noqa: F401,E402
import app.features.training.training_model  # noqa: F401,E402
import app.features.training_users.training_users_model  # noqa: F401,E402
import app.features.training_segments.training_segments_model  # noqa: F401,E402
import app.features.tournament.tournament_model  # noqa: F401,E402
import app.features.tournament_users.tournament_users_model  # noqa: F401,E402
import app.features.season.season_model  # noqa: F401,E402
import app.features.membership.membership_model  # noqa: F401,E402
import app.features.contract.contract_model  # noqa: F401,E402
import app.features.contract_installment.contract_installment_model  # noqa: F401,E402
import app.features.wallet.wallet_model  # noqa: F401,E402
import app.features.payment.payment_model  # noqa: F401,E402

from sqlalchemy import text  # noqa: E402

from app.core.db.database import SessionLocal  # noqa: E402


# Cleared. Order is irrelevant — one TRUNCATE statement resolves the foreign
# keys itself. CASCADE is only a safety net: every table that references one of
# these is already in the list, so it pulls in nothing extra.
TRUNCATE_TABLES = [
    "payment",
    "contract_installment",
    "contract",
    "group_user",
    "group",
    "membership",
    "season",
    "training",
    "training_users",
    "training_segment",
    "segment_exercise",
    "segment_sparring",
    "sparring_participant",
    "sparring_event",
    "tournament",
    "tournament_users",
]

# Kept. Printed after the truncate so you can see they survived untouched.
KEPT_TABLES = [
    "users",
    "company",
    "wallet",
    "country",
    "city",
    "selection",
    "exercise_option",
    "income_category",
    "expense_category",
]


def quoted(table):
    """`group` is a reserved SQL word, so every table name gets quoted."""
    return f'"{table}"'


def row_counts(db, tables):
    counts = {}
    for table in tables:
        counts[table] = db.execute(
            text(f"SELECT count(*) FROM {quoted(table)}")
        ).scalar()
    return counts


def print_counts(title, counts):
    print(f"  {title}")
    for table, count in counts.items():
        print(f"    {table:<22} {count:>5} rows")


def confirm(total):
    print(
        f"\nThis deletes {total} rows from {len(TRUNCATE_TABLES)} tables. "
        "Tables and schema are kept."
    )
    answer = input("Type 'yes' to continue: ").strip().lower()
    return answer == "yes"


def reset(skip_confirm=False):
    db = SessionLocal()
    try:
        before = row_counts(db, TRUNCATE_TABLES)
        total = sum(before.values())

        print("Clearing transactional data...\n")
        print_counts("BEFORE", before)

        if total == 0:
            print("\nNothing to clear — every target table is already empty.")
            return

        if not skip_confirm and not confirm(total):
            print("Aborted. Nothing was changed.")
            return

        table_list = ", ".join(quoted(t) for t in TRUNCATE_TABLES)
        db.execute(text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE"))
        db.commit()

        print()
        print_counts("AFTER", row_counts(db, TRUNCATE_TABLES))
        print()
        print_counts("KEPT", row_counts(db, KEPT_TABLES))

        print(f"\nDone. Cleared {total} rows, schema untouched.")
        print("Re-seed with: python seed_dev_data.py")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    reset(skip_confirm="--yes" in sys.argv)
