"""
Minimal base seed — the smallest set of rows needed to log in and work.

Creates:

  * country  Srbija
  * city     Beograd (in Srbija)
  * company  VK Beograd (CLUB, in Beograd/Srbija) + its COMPANY wallet
  * user     Aleksandar Stevanovic (SUPER_ADMIN, in VK Beograd) + his USER wallet

Nothing else — no seasons, selections, contracts or demo users. For the full
billing-domain dataset use seed_dev_data.py instead.

Every step is find-or-create, so re-running changes nothing the second time.

Run with: python seed_base_data.py
"""

import os
import sys
from datetime import date

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
import app.features.season_selection_user.season_selection_user_model  # noqa: F401,E402
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

from app.core.db.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.features.company.company_model import Company, CompanyType  # noqa: E402
from app.features.sifarnici.city.city_model import City  # noqa: E402
from app.features.sifarnici.country.country_model import Country  # noqa: E402
from app.features.users.users_models import User, UserRole  # noqa: E402
from app.features.wallet.wallet_model import Wallet, WalletOwnerType  # noqa: E402


COUNTRY_NAME = "Srbija"
CITY_NAME = "Beograd"
COMPANY_NAME = "VK Beograd"

USER_EMAIL = "aleksandar.stevanovic@gmail.com"
USER_USERNAME = "aleksandar.stevanovic"
USER_PASSWORD = "Password123!"
USER_FIRST_NAME = "Aleksandar"
USER_LAST_NAME = "Stevanovic"
USER_PHONE = "000000000"
USER_DOB = date(1990, 1, 1)


def get_or_create_wallet(db, owner_id, owner_type, name):
    wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == owner_id, Wallet.owner_type == owner_type)
        .first()
    )
    if wallet:
        return wallet
    wallet = Wallet(owner_id=owner_id, owner_type=owner_type, name=name)
    db.add(wallet)
    db.flush()
    return wallet


def get_or_create_country(db, name):
    country = db.query(Country).filter(Country.name == name).first()
    if country:
        print(f"  [COUNTRY] already exists {name} (id={country.id})")
        return country
    country = Country(name=name, is_active=True)
    db.add(country)
    db.flush()
    print(f"  [COUNTRY] created {name} (id={country.id})")
    return country


def get_or_create_city(db, name, country):
    city = (
        db.query(City)
        .filter(City.name == name, City.country_id == country.id)
        .first()
    )
    if city:
        print(f"  [CITY]    already exists {name} (id={city.id})")
        return city
    city = City(name=name, country_id=country.id, is_active=True)
    db.add(city)
    db.flush()
    print(f"  [CITY]    created {name} (id={city.id})")
    return city


def get_or_create_company(db, name, company_type, city, country):
    company = db.query(Company).filter(Company.name == name).first()
    if company:
        print(f"  [COMPANY] already exists {name} (id={company.id})")
    else:
        company = Company(
            name=name,
            company_type=company_type.value,
            city_id=city.id,
            country_id=country.id,
            is_active=True,
        )
        db.add(company)
        db.flush()
        print(f"  [COMPANY] created {name} ({company_type.value}, id={company.id})")

    if company.w_id is None:
        wallet = get_or_create_wallet(
            db, company.id, WalletOwnerType.COMPANY, company.name
        )
        company.w_id = wallet.id
        print(f"  [WALLET]  company wallet {wallet.id} → {company.name}")
    else:
        print(f"  [WALLET]  company wallet already linked ({company.w_id})")

    return company


def get_or_create_user(db, company):
    user = db.query(User).filter(User.email == USER_EMAIL).first()
    if user:
        print(f"  [USER]    already exists {USER_EMAIL} (id={user.id})")
    else:
        user = User(
            email=USER_EMAIL,
            username=USER_USERNAME,
            hashed_password=hash_password(USER_PASSWORD),
            first_name=USER_FIRST_NAME,
            last_name=USER_LAST_NAME,
            phone_number=USER_PHONE,
            date_of_birth=USER_DOB,
            company_id=company.id,
            roles=[UserRole.SUPER_ADMIN.value],
            is_active=True,
        )
        db.add(user)
        db.flush()
        print(f"  [USER]    created {USER_EMAIL} (SUPER_ADMIN, id={user.id})")

    if user.w_id is None:
        wallet = get_or_create_wallet(
            db,
            user.id,
            WalletOwnerType.USER,
            f"{user.first_name} {user.last_name}",
        )
        user.w_id = wallet.id
        print(f"  [WALLET]  user wallet {wallet.id} → {user.email}")
    else:
        print(f"  [WALLET]  user wallet already linked ({user.w_id})")

    return user


def seed():
    db = SessionLocal()
    try:
        print("Seeding base data...")
        country = get_or_create_country(db, COUNTRY_NAME)
        city = get_or_create_city(db, CITY_NAME, country)
        company = get_or_create_company(
            db, COMPANY_NAME, CompanyType.CLUB, city, country
        )
        user = get_or_create_user(db, company)

        db.commit()

        print("\nDone.")
        print(f"  country id={country.id} name={country.name}")
        print(f"  city    id={city.id} name={city.name}")
        print(f"  company id={company.id} name={company.name} w_id={company.w_id}")
        print(f"  user    id={user.id} email={user.email} w_id={user.w_id}")
        print(f"\nLogin: {USER_EMAIL} / {USER_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
