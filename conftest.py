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
from datetime import date, datetime, timezone
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
        company_id=None,
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
def create_training(db_session):
    """Factory fixture to create a training in the DB."""
    def _create(company_id, **kwargs):
        defaults = {
            "start_training_date_time": datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            "end_training_date_time": datetime(2026, 4, 1, 11, 0, tzinfo=timezone.utc),
            "price": 100,
            "payed": False,
            "status": TrainingStatus.INCOMING.value,
        }
        defaults.update(kwargs)
        training = Training(company_id=company_id, **defaults)
        db_session.add(training)
        db_session.commit()
        db_session.refresh(training)
        return training
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
def super_admin_headers(create_user, mock_redis):
    """Return Authorization headers for a SUPER_ADMIN user."""
    from app.core.security import create_access_token

    user = create_user(
        email="super@test.com",
        username="superadmin",
        roles=[UserRole.SUPER_ADMIN],
    )
    token = create_access_token({
        "sub": user.email,
        "user_id": user.id,
        "roles": user.roles,
        "type": "access",
    })
    mock_redis["store_access_token"](user.id, token)

    return {"Authorization": f"Bearer {token}"}, user
