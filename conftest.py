# ============================================
# TEST CONFIGURATION - Shared Fixtures
# ============================================
# This file is automatically loaded by pytest.
# Fixtures defined here are available to ALL tests.
#
# WHAT IT DOES:
# - Creates an in-memory SQLite database for tests
# - Overrides FastAPI's get_db dependency
# - Provides a TestClient for calling API endpoints
# - Provides helper factories for creating test data
# ============================================

import pytest
from datetime import date, datetime, time, timezone
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.core.db.base import Base
from app.core.db.database import get_db
from app.main import app
from app.features.users.users_models import User, UserRole
from app.features.company.company_model import Company
from app.features.sifarnici.country.country_model import Country
from app.features.training.training_model import Training, TrainingStatus
from app.features.season.season_model import Season
from app.features.sifarnici.selection.selection_model import Selection  # noqa: F401
from app.features.season_selection_user.season_selection_user_model import (  # noqa: F401
    SeasonSelectionUser,
)
from app.features.membership.membership_model import Membership  # noqa: F401
from app.features.contract.contract_model import Contract  # noqa: F401
from app.features.contract_installment.contract_installment_model import (  # noqa: F401
    ContractInstallment,
)


# ============================================
# TEST DATABASE (in-memory SQLite)
# ============================================
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ============================================
# FIXTURES
# ============================================

@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """
    Turn off rate limiting / duplicate-request guards for the test suite.

    Tests fire many identical requests back to back, which is exactly what
    the production guards are built to reject. Tests that specifically
    exercise the limiter can flip the flag back on themselves.
    """
    from app.core.config import settings
    from app.core import rate_limit

    original = settings.RATE_LIMIT_ENABLED
    settings.RATE_LIMIT_ENABLED = False
    rate_limit._local_counters.clear()
    yield
    settings.RATE_LIMIT_ENABLED = original


@pytest.fixture()
def db_session() -> Session:
    """Provide a clean database session for each test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session) -> TestClient:
    """
    Provide a FastAPI TestClient with DB dependency overridden.
    Redis calls are mocked so tests don't need a running Redis.
    """
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    with patch("app.core.redis.redis_client", MagicMock()):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


# ============================================
# MOCK REDIS FIXTURE
# ============================================

@pytest.fixture()
def mock_redis():
    """Mock Redis functions used by auth."""
    with patch("app.features.auth.auth_service.store_access_token") as mock_store_at, \
         patch("app.features.auth.auth_service.store_refresh_token") as mock_store_rt, \
         patch("app.features.auth.auth_service.get_refresh_token") as mock_get_rt, \
         patch("app.features.auth.auth_service.delete_user_tokens") as mock_del:
        yield {
            "store_access_token": mock_store_at,
            "store_refresh_token": mock_store_rt,
            "get_refresh_token": mock_get_rt,
            "delete_user_tokens": mock_del,
        }


# ============================================
# FROZEN "TODAY" FIXTURE
# ============================================

@pytest.fixture()
def freeze_club_today(monkeypatch):
    """Freeze the club-local "today" the contract service uses to compute
    statuses. Call it with a date; call it again to move time forward."""
    def _freeze(d):
        monkeypatch.setattr(
            "app.features.contract.contract_service.club_today", lambda: d
        )
        return d
    return _freeze


# ============================================
# FACTORY FIXTURES
# ============================================

@pytest.fixture()
def create_company(db_session):
    """Factory fixture to create a company in the DB."""
    def _create(name="Test Club", **kwargs):
        company = Company(name=name, **kwargs)
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)
        return company
    return _create


@pytest.fixture()
def create_country(db_session):
    """Factory fixture to create a country in the DB."""
    def _create(name="Test Country", **kwargs):
        country = Country(name=name, **kwargs)
        db_session.add(country)
        db_session.commit()
        db_session.refresh(country)
        return country
    return _create


@pytest.fixture()
def create_user(db_session):
    """Factory fixture to create a user in the DB."""
    def _create(
        email="test@test.com",
        username="testuser",
        password="hashedpass",
        first_name="Test",
        last_name="User",
        phone_number="123456",
        date_of_birth=date(2000, 1, 1),
        roles=None,
        company_id=None,  # required by the DB (NOT NULL); callers must pass one
        is_active=True,
        **kwargs,
    ):
        import bcrypt
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = User(
            email=email,
            username=username,
            hashed_password=hashed,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            date_of_birth=date_of_birth,
            roles=[r.value for r in (roles or [UserRole.USER])],
            company_id=company_id,
            is_active=is_active,
            **kwargs,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    return _create


@pytest.fixture()
def create_season(db_session):
    """Factory fixture to create a season in the DB."""
    def _create(company_id, name="2026 Season",
                start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
                is_current=True, **kwargs):
        season = Season(
            company_id=company_id,
            name=name,
            start_date=start_date,
            end_date=end_date,
            is_current=is_current,
            **kwargs,
        )
        db_session.add(season)
        db_session.commit()
        db_session.refresh(season)
        return season
    return _create


@pytest.fixture()
def ensure_season(db_session):
    """Find-or-create the season covering a company + date (used by factories)."""
    def _ensure(company_id, d):
        season = (
            db_session.query(Season)
            .filter(
                Season.company_id == company_id,
                Season.start_date <= d,
                Season.end_date >= d,
            )
            .first()
        )
        if season is None:
            season = Season(
                company_id=company_id,
                name=f"{d.year} Season",
                start_date=date(d.year, 1, 1),
                end_date=date(d.year, 12, 31),
                is_current=True,
            )
            db_session.add(season)
            db_session.commit()
            db_session.refresh(season)
        return season
    return _ensure


@pytest.fixture()
def create_training(db_session, ensure_season):
    """Factory fixture to create a training in the DB.

    pool_id and season_id are NOT NULL on the model, so defaults are supplied:
    the pool defaults to the training's own company, and the season covering the
    training's date is found-or-created.
    """
    def _create(company_id, pool_id=None, **kwargs):
        defaults = {
            "training_date": date(2026, 4, 1),
            "start_time": time(10, 0),
            "end_time": time(11, 0),
            "price": 100,
            "status": TrainingStatus.INCOMING.value,
            "pool_id": pool_id if pool_id is not None else company_id,
        }
        defaults.update(kwargs)
        season = ensure_season(company_id, defaults["training_date"])
        training = Training(company_id=company_id, season_id=season.id, **defaults)
        db_session.add(training)
        db_session.commit()
        db_session.refresh(training)
        return training
    return _create


@pytest.fixture()
def create_exercise_option(db_session):
    """Factory fixture to create an exercise_option (sifarnik) in the DB."""
    def _create(segment_type, company_id, code="freestyle", name="Freestyle", **kwargs):
        from app.features.sifarnici.exercise_option.exercise_option_model import ExerciseOption

        option = ExerciseOption(
            segment_type=segment_type, company_id=company_id, code=code, name=name, **kwargs
        )
        db_session.add(option)
        db_session.commit()
        db_session.refresh(option)
        return option
    return _create


# ============================================
# AUTH HELPER FIXTURES
# ============================================

@pytest.fixture()
def auth_headers(create_company, create_user, mock_redis):
    """
    Return Authorization headers for a default admin user.
    Useful for testing protected endpoints.
    """
    from app.core.security import create_access_token

    company = create_company()
    user = create_user(
        email="admin@test.com",
        username="admin",
        roles=[UserRole.ADMIN],
        company_id=company.id,
    )
    token = create_access_token({
        "sub": user.email,
        "user_id": user.id,
        "roles": user.roles,
        "type": "access",
    })

    # Make the mock return this token so auth dependency passes
    mock_redis["store_access_token"](user.id, token)

    return {"Authorization": f"Bearer {token}"}, user, company


@pytest.fixture()
def super_admin_headers(create_company, create_user, mock_redis):
    """Return Authorization headers for a SUPER_ADMIN user."""
    from app.core.security import create_access_token

    company = create_company(name="Super Admin Company")
    user = create_user(
        email="super@test.com",
        username="superadmin",
        roles=[UserRole.SUPER_ADMIN],
        company_id=company.id,
    )
    token = create_access_token({
        "sub": user.email,
        "user_id": user.id,
        "roles": user.roles,
        "type": "access",
    })
    mock_redis["store_access_token"](user.id, token)

    return {"Authorization": f"Bearer {token}"}, user
