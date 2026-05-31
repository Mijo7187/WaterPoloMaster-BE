"""
Idempotent seed script for payment_type, expense_category, income_category.
Run with:  python seed_payment_data.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.core.db.database import SessionLocal
from app.features.payment.payment_model import Payment  # noqa: F401  (mapper registration)
from app.features.sifarnici.expense_category.expense_category_model import ExpenseCategory
from app.features.sifarnici.income_category.income_category_model import IncomeCategory
from app.features.sifarnici.payment_type.payment_type_model import PaymentType, PaymentTypeCode
from app.features.wallet.wallet_model import Wallet, WalletOwnerType  # noqa: F401


PAYMENT_TYPES = [
    {
        "code": PaymentTypeCode.USER_QUARTERLY_FEE,
        "name": "User Quarterly Fee",
        "sender_type": WalletOwnerType.USER,
        "receiver_type": WalletOwnerType.COMPANY,
    },
    {
        "code": PaymentTypeCode.USER_TOURNAMENT_FEE,
        "name": "User Tournament Fee",
        "sender_type": WalletOwnerType.USER,
        "receiver_type": WalletOwnerType.COMPANY,
    },
    {
        "code": PaymentTypeCode.CLUB_TOURNAMENT_POOL,
        "name": "Club Tournament Pool",
        "sender_type": WalletOwnerType.COMPANY,
        "receiver_type": WalletOwnerType.COMPANY,
    },
    {
        "code": PaymentTypeCode.CLUB_SALARY_USER,
        "name": "Club Salary User",
        "sender_type": WalletOwnerType.COMPANY,
        "receiver_type": WalletOwnerType.USER,
    },
    {
        "code": PaymentTypeCode.CLUB_TRAINING_POOL,
        "name": "Club Training Pool",
        "sender_type": WalletOwnerType.COMPANY,
        "receiver_type": WalletOwnerType.COMPANY,
    },
]

EXPENSE_CATEGORIES = ["Travel", "Equipment", "Other", "Party", "Maintenance", "Fees"]
INCOME_CATEGORIES = ["Sponsorship", "Donation", "Reimbursement", "Other"]


def seed(db):
    # ── payment_type ────────────────────────────────────────────
    for pt in PAYMENT_TYPES:
        existing = db.query(PaymentType).filter(PaymentType.code == pt["code"]).first()
        if not existing:
            row = PaymentType(
                name=pt["name"],
                code=pt["code"],
                sender_type=pt["sender_type"],
                receiver_type=pt["receiver_type"],
                active=True,
            )
            db.add(row)
            print(f"  [payment_type] inserted: {pt['code'].value}")
        else:
            existing.name = pt["name"]
            existing.sender_type = pt["sender_type"]
            existing.receiver_type = pt["receiver_type"]
            print(f"  [payment_type] already exists, updated: {pt['code'].value}")

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
