# ============================================
# AUTH TESTS
# ============================================

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from app.features.auth.auth_service import AuthService
from app.features.users.users_models import UserRole


# ============================================
# AUTH SERVICE TESTS
# ============================================

class TestAuthServiceAuthenticate:
    """Tests for AuthService.authenticate_user"""

    def test_authenticate_valid_credentials(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(
            email="auth@test.com",
            username="authuser",
            password="testpass",
            company_id=company.id,
        )
        service = AuthService(db_session)
        result = service.authenticate_user("auth@test.com", "testpass")
        assert result is not None
        assert result.email == "auth@test.com"

    def test_authenticate_wrong_password(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="auth@test.com", password="testpass", company_id=company.id)
        service = AuthService(db_session)
        result = service.authenticate_user("auth@test.com", "wrongpass")
        assert result is None

    def test_authenticate_nonexistent_email(self, db_session):
        service = AuthService(db_session)
        result = service.authenticate_user("nobody@test.com", "testpass")
        assert result is None

    def test_authenticate_inactive_user(self, db_session, create_company, create_user):
        company = create_company()
        create_user(
            email="inactive@test.com",
            username="inactiveuser",
            password="testpass",
            company_id=company.id,
            is_active=False,
        )
        service = AuthService(db_session)
        result = service.authenticate_user("inactive@test.com", "testpass")
        assert result is None


class TestAuthServiceTokens:
    """Tests for token creation and verification"""

    def test_create_access_token(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="token@test.com", company_id=company.id)
        service = AuthService(db_session)
        token = service.create_access_token(user)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="refresh@test.com", company_id=company.id)
        service = AuthService(db_session)
        token = service.create_refresh_token(user)
        assert token is not None
        assert isinstance(token, str)

    def test_create_tokens_returns_both(self, db_session, create_company, create_user, mock_redis):
        company = create_company()
        user = create_user(email="both@test.com", company_id=company.id)
        service = AuthService(db_session)
        tokens = service.create_tokens(user)
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["access_token"] != tokens["refresh_token"]

    def test_verify_refresh_token_valid(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="verify@test.com", company_id=company.id)
        service = AuthService(db_session)
        token = service.create_refresh_token(user)
        payload = service.verify_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == "verify@test.com"
        assert payload["type"] == "refresh"

    def test_verify_refresh_token_invalid(self, db_session):
        service = AuthService(db_session)
        result = service.verify_refresh_token("invalid.token.here")
        assert result is None

    def test_verify_access_token_as_refresh_fails(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="wrongtype@test.com", company_id=company.id)
        service = AuthService(db_session)
        access_token = service.create_access_token(user)
        result = service.verify_refresh_token(access_token)
        assert result is None


class TestAuthServiceRefresh:
    """Tests for refresh_access_token"""

    def test_refresh_with_valid_token(self, db_session, create_company, create_user, mock_redis):
        company = create_company()
        user = create_user(email="refresh@test.com", company_id=company.id)
        service = AuthService(db_session)
        tokens = service.create_tokens(user)

        mock_redis["get_refresh_token"].return_value = tokens["refresh_token"]
        new_tokens = service.refresh_access_token(tokens["refresh_token"])
        assert new_tokens is not None
        assert "access_token" in new_tokens

    def test_refresh_with_invalid_token(self, db_session, mock_redis):
        service = AuthService(db_session)
        result = service.refresh_access_token("bad.token")
        assert result is None

    def test_refresh_token_mismatch_redis(self, db_session, create_company, create_user, mock_redis):
        company = create_company()
        user = create_user(email="mismatch@test.com", company_id=company.id)
        service = AuthService(db_session)
        tokens = service.create_tokens(user)

        mock_redis["get_refresh_token"].return_value = "different_token"
        result = service.refresh_access_token(tokens["refresh_token"])
        assert result is None


class TestAuthServiceLogout:
    """Tests for logout"""

    def test_logout_calls_delete(self, mock_redis):
        AuthService.logout(42)
        mock_redis["delete_user_tokens"].assert_called_once_with(42)


# ============================================
# AUTH ROUTER / ENDPOINT TESTS
# ============================================

class TestLoginEndpoint:
    """Tests for POST /auth/login"""

    def test_login_success(self, client, db_session, create_company, create_user):
        with patch("app.core.redis.redis_client"):
            with patch("app.features.auth.auth_service.store_access_token"), \
                 patch("app.features.auth.auth_service.store_refresh_token"):
                company = create_company()
                create_user(
                    email="login@test.com",
                    username="loginuser",
                    password="testpass",
                    company_id=company.id,
                )
                response = client.post("/api/auth/login", json={
                    "email": "login@test.com",
                    "password": "testpass",
                })
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == 200
                assert data["data"]["access_token"]
                assert data["data"]["refresh_token"]

    def test_login_wrong_password(self, client, db_session, create_company, create_user):
        company = create_company()
        create_user(email="login@test.com", password="testpass", company_id=company.id)
        response = client.post("/api/auth/login", json={
            "email": "login@test.com",
            "password": "wrongpass",
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post("/api/auth/login", json={
            "email": "nobody@test.com",
            "password": "testpass",
        })
        assert response.status_code == 401

    def test_login_invalid_email_format(self, client):
        response = client.post("/api/auth/login", json={
            "email": "not-an-email",
            "password": "testpass",
        })
        assert response.status_code == 422


class TestRefreshEndpoint:
    """Tests for POST /auth/refresh"""

    def test_refresh_invalid_token(self, client):
        response = client.post("/api/auth/refresh", json={
            "refresh_token": "invalid.token.value",
        })
        assert response.status_code == 401


class TestLogoutEndpoint:
    """Tests for POST /auth/logout"""

    def test_logout_without_auth(self, client):
        response = client.post("/api/auth/logout")
        assert response.status_code in (401, 403)
