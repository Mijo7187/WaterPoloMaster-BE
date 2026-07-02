"""
Seed script: create a wallet for every user and company that doesn't have one.
Run with: python seed_wallets.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import app.features.sifarnici.country.country_model
import app.features.sifarnici.city.city_model
import app.features.sifarnici.payment_type.payment_type_model
import app.features.sifarnici.training_type.training_type_model
import app.features.sifarnici.swimming_discipline.swimming_discipline_model
import app.features.sifarnici.expense_category.expense_category_model
import app.features.sifarnici.income_category.income_category_model
import app.features.wallet.wallet_model
import app.features.payment.payment_model
import app.features.company.company_model
import app.features.users.users_models
import app.features.training.training_model
import app.features.training_users_list.training_users_list_model

from app.core.db.database import SessionLocal
from app.features.users.users_models import User
from app.features.company.company_model import Company
from app.features.wallet.wallet_model import Wallet, WalletOwnerType


def seed_wallets():
    db = SessionLocal()
    try:
        users_created = 0
        companies_created = 0

        def get_or_create_wallet(owner_id, owner_type, name):
            existing = (
                db.query(Wallet)
                .filter(Wallet.owner_id == owner_id, Wallet.owner_type == owner_type)
                .first()
            )
            if existing:
                if existing.name is None:
                    existing.name = name
                return existing, False
            wallet = Wallet(owner_id=owner_id, owner_type=owner_type, name=name)
            db.add(wallet)
            db.flush()
            return wallet, True

        # --- Users ---
        users = db.query(User).all()
        for user in users:
            if user.w_id is None:
                name = f"{user.first_name} {user.last_name}"
                wallet, created = get_or_create_wallet(user.id, WalletOwnerType.USER, name)
                user.w_id = wallet.id
                users_created += 1
                label = "created" if created else "linked existing"
                print(f"  [USER]    id={user.id} {user.email} → {label} wallet {wallet.id} name='{name}'")

        # --- Companies ---
        companies = db.query(Company).all()
        for company in companies:
            if company.w_id is None:
                wallet, created = get_or_create_wallet(company.id, WalletOwnerType.COMPANY, company.name)
                company.w_id = wallet.id
                companies_created += 1
                label = "created" if created else "linked existing"
                print(f"  [COMPANY] id={company.id} {company.name} → {label} wallet {wallet.id} name='{company.name}'")

        # --- Backfill names on existing linked wallets ---
        backfilled = 0
        for user in db.query(User).filter(User.w_id.isnot(None)).all():
            wallet = db.get(Wallet, user.w_id)
            if wallet and wallet.name is None:
                wallet.name = f"{user.first_name} {user.last_name}"
                backfilled += 1
                print(f"  [BACKFILL USER]    {user.email} → name='{wallet.name}'")

        for company in db.query(Company).filter(Company.w_id.isnot(None)).all():
            wallet = db.get(Wallet, company.w_id)
            if wallet and wallet.name is None:
                wallet.name = company.name
                backfilled += 1
                print(f"  [BACKFILL COMPANY] {company.name} → name='{wallet.name}'")

        db.commit()
        print(f"\nDone. Created {users_created} user wallet(s) and {companies_created} company wallet(s). Backfilled {backfilled} name(s).")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding wallets...")
    seed_wallets()
