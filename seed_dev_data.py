"""
Idempotent dev seed for the billing domain.

Creates the minimum a developer needs to exercise the
membership + contract → contract_installment chain:

  * one CLUB company and one POOL company, each with a wallet
  * an admin user and two player users, each with a wallet
  * one season, marked is_current (trainings and tournaments hang off it)
  * two selections (U15, Masters) — the age-group catalog
  * membership rows for BOTH programs and BOTH billing types — a plan prices
    one selection, either MONTHLY (open-ended) or TERM (one fixed block)
  * one MONTHLY and one TERM contract, so both generation paths are covered,
    each with the installment(s) the machine wrote at signing
  * the group (season + selection) each contract's player was enrolled in

Safe to re-run after a reset: every step is find-or-create, so running it twice
changes nothing the second time.

Run with: python seed_dev_data.py
"""

import os
import sys
from datetime import date, datetime
from decimal import Decimal

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

from app.core.db.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.features.company.company_model import Company, CompanyType  # noqa: E402
from app.features.contract.contract_model import (  # noqa: E402
    Contract,
    ContractType,
)
from app.features.contract.contract_schemas import ContractCreate  # noqa: E402
from app.features.contract.contract_service import ContractService  # noqa: E402
from app.features.membership.membership_model import (  # noqa: E402
    BillingType,
    Membership,
    Program,
)
from app.features.season.season_model import Season  # noqa: E402
from app.features.sifarnici.selection.selection_model import Selection  # noqa: E402
from app.features.users.users_models import User, UserRole  # noqa: E402
from app.features.wallet.wallet_model import Wallet, WalletOwnerType  # noqa: E402


SEASON_NAME = "2026 Season"
SEASON_START = date(2026, 1, 1)
SEASON_END = date(2026, 12, 31)


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


def get_or_create_company(db, name, company_type):
    company = db.query(Company).filter(Company.name == name).first()
    if not company:
        company = Company(name=name, company_type=company_type.value)
        db.add(company)
        db.flush()
        print(f"  [COMPANY] created {name} ({company_type.value})")

    if company.w_id is None:
        company.w_id = get_or_create_wallet(
            db, company.id, WalletOwnerType.COMPANY, company.name
        ).id
    return company


def get_or_create_user(db, email, first_name, last_name, company, roles, dob):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            username=email.split("@")[0],
            hashed_password=hash_password("Password123!"),
            first_name=first_name,
            last_name=last_name,
            phone_number="000000000",
            date_of_birth=dob,
            company_id=company.id,
            roles=[r.value for r in roles],
            is_active=True,
        )
        db.add(user)
        db.flush()
        print(f"  [USER]    created {email} ({', '.join(r.value for r in roles)})")

    if user.w_id is None:
        user.w_id = get_or_create_wallet(
            db, user.id, WalletOwnerType.USER, f"{first_name} {last_name}"
        ).id
    return user


def get_or_create_season(db, company):
    season = (
        db.query(Season)
        .filter(Season.company_id == company.id, Season.name == SEASON_NAME)
        .first()
    )
    if not season:
        season = Season(
            company_id=company.id,
            name=SEASON_NAME,
            start_date=SEASON_START,
            end_date=SEASON_END,
            is_current=True,
        )
        db.add(season)
        db.flush()
        print(f"  [SEASON]  created {SEASON_NAME}")
    return season


def get_or_create_selection(db, company, name, age_min=None, age_max=None):
    selection = (
        db.query(Selection)
        .filter(Selection.company_id == company.id, Selection.name == name)
        .first()
    )
    if not selection:
        selection = Selection(
            company_id=company.id, name=name, age_min=age_min, age_max=age_max
        )
        db.add(selection)
        db.flush()
        print(f"  [SELECT]  created {name}")
    return selection


def get_or_create_membership(
    db, company, selection, name, program, billing_type, price, term_months=None
):
    """One plan per (company, selection, program, billing_type) — the catalog key."""
    row = (
        db.query(Membership)
        .filter(
            Membership.company_id == company.id,
            Membership.selection_id == selection.id,
            Membership.program == program,
            Membership.billing_type == billing_type,
        )
        .first()
    )
    if not row:
        row = Membership(
            company_id=company.id,
            selection_id=selection.id,
            name=name,
            program=program,
            billing_type=billing_type,
            price=price,
            term_months=term_months,
        )
        db.add(row)
        db.flush()
        shape = (
            f"{price}/month, open-ended"
            if billing_type == BillingType.MONTHLY
            else f"{price} for a {term_months}-month block"
        )
        print(f"  [MEMBER]  created {name} ({program.value}) = {shape}")
    return row


def get_or_create_contract(db, company, user, membership):
    contract = (
        db.query(Contract)
        .filter(Contract.company_id == company.id, Contract.user_id == user.id)
        .first()
    )
    if contract:
        return contract, False

    # Created through the service, which snapshots billing_type / amount /
    # term_months off the plan and writes the period(s) owed. The terms are
    # copied here, not read from the catalog later — editing the membership
    # must not move an already-signed contract.
    contract = ContractService(db).create(ContractCreate(
        company_id=company.id,
        user_id=user.id,
        contract_type=ContractType.MEMBERSHIP,
        membership_id=membership.id,
        # end_date and status are derived: null for MONTHLY, start + term for
        # TERM, and the status those dates imply today.
        start_date=SEASON_START,
        signed_at=datetime.now(),
    ))
    print(f"  [CONTRACT] created for {user.email}")
    return contract, True


def seed():
    db = SessionLocal()
    try:
        club = get_or_create_company(db, "WaterPolo Dev Club", CompanyType.CLUB)
        get_or_create_company(db, "Dev City Pool", CompanyType.POOL)
        db.flush()

        admin = get_or_create_user(
            db, "admin@dev.local", "Ana", "Admin", club,
            [UserRole.ADMIN], date(1990, 1, 1),
        )
        player_one = get_or_create_user(
            db, "player1@dev.local", "Petar", "Player", club,
            [UserRole.PLAYER, UserRole.USER], date(2011, 5, 20),
        )
        player_two = get_or_create_user(
            db, "player2@dev.local", "Marko", "Plivac", club,
            [UserRole.PLAYER, UserRole.USER], date(2010, 9, 3),
        )

        get_or_create_season(db, club)

        u15 = get_or_create_selection(db, club, "U15", age_min=13, age_max=15)
        masters = get_or_create_selection(db, club, "Masters", age_min=35)

        # The price catalog. A plan prices ONE selection and says how it bills:
        # MONTHLY keeps charging until the contract is cancelled, TERM is a
        # single block you re-sign for.
        u15_waterpolo = get_or_create_membership(
            db, club, u15, "U15 Waterpolo", Program.WATERPOLO,
            BillingType.MONTHLY, price=Decimal("5000.00"),
        )
        get_or_create_membership(
            db, club, u15, "U15 Swimming", Program.SWIMMING,
            BillingType.MONTHLY, price=Decimal("3000.00"),
        )
        masters_waterpolo = get_or_create_membership(
            db, club, masters, "Masters Waterpolo", Program.WATERPOLO,
            BillingType.TERM, price=Decimal("15000.00"), term_months=3,
        )
        get_or_create_membership(
            db, club, masters, "Masters Swimming", Program.SWIMMING,
            BillingType.TERM, price=Decimal("7500.00"), term_months=3,
        )

        # One of each billing type, so both generation paths are seeded. Each
        # also enrols its player in the current season's group.
        get_or_create_contract(db, club, player_one, u15_waterpolo)
        get_or_create_contract(db, club, player_two, masters_waterpolo)

        db.commit()
        print(f"\nDone. Admin login: {admin.email} / Password123!")

    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding dev data...")
    seed()
