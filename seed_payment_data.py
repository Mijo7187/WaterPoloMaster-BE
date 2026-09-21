"""
Idempotent seed script for expense_category, income_category.

Payment types are no longer seeded — they live entirely in code as the
`PaymentTypeCode` enum + `PAYMENT_TYPE_SPECS` registry in payment_model.py.

Run with:  python seed_payment_data.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.core.db.database import SessionLocal
from app.features.payment.payment_model import Payment  # noqa: F401  (mapper registration)
from app.features.sifarnici.expense_category.expense_category_model import ExpenseCategory
from app.features.sifarnici.income_category.income_category_model import IncomeCategory
from app.features.wallet.wallet_model import Wallet, WalletOwnerType  # noqa: F401


EXPENSE_CATEGORIES = ["Travel", "Equipment", "Other", "Party", "Maintenance", "Fees"]
INCOME_CATEGORIES = ["Sponsorship", "Donation", "Reimbursement", "Other"]


def seed(db):
    # ── expense_category (global, wallet_id = NULL) ─────────────
    for label in EXPENSE_CATEGORIES:
        existing = (
            db.query(ExpenseCategory)
            .filter(ExpenseCategory.label == label, ExpenseCategory.wallet_id.is_(None))
            .first()
        )
        if not existing:
            db.add(ExpenseCategory(label=label, wallet_id=None, is_active=True))
            print(f"  [expense_category] inserted: {label}")
        else:
            print(f"  [expense_category] already exists: {label}")

    # ── income_category (global, wallet_id = NULL) ──────────────
    for label in INCOME_CATEGORIES:
        existing = (
            db.query(IncomeCategory)
            .filter(IncomeCategory.label == label, IncomeCategory.wallet_id.is_(None))
            .first()
        )
        if not existing:
            db.add(IncomeCategory(label=label, wallet_id=None, is_active=True))
            print(f"  [income_category] inserted: {label}")
        else:
            print(f"  [income_category] already exists: {label}")

    db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        print("Seeding payment data...")
        seed(db)
    finally:
        db.close()
