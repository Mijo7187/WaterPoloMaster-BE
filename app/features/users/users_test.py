# ============================================
# USERS TESTS
# ============================================

import pytest
from datetime import date

from app.features.users.users_service import UserService
from app.features.users.users_schemas import UserCreate, UserUpdate, UserFilters
from app.features.users.users_repository import UserRepository
from app.features.users.users_models import User, UserRole
from app.core.api.exceptions import NotFoundException, ConflictException, BadRequestException


# ============================================
# USER REPOSITORY TESTS
# ============================================
# {
#     "user_id": 42111,
#     "pan_tail": "0100",
#     "user_name": "Marko Radojcic",
#     "checked": false,
#     "name": "1 mesec fitnes neograničeno",
#     "number_of_installment": 1,
#     "amount": 3800,
#     "package_id": 8,
#     "location": "Zemun",
#     "comment": "None",
#     "id": 167198,
#     "date_of_payment": "2024-12-09 11:58:02",
#     "income_type": "package",
#     "staff_name": null,
#     "expense_subgroup": null
# }


class TestUserRepository:

    def test_create_user(self, db_session, create_company):
        company = create_company()
        repo = UserRepository(db_session)
        user = repo.create({
            "email": "repo@test.com",
            "username": "repouser",
            "hashed_password": "hashed",
            "first_name": "Repo",
            "last_name": "User",
            "phone_number": "123",
            "date_of_birth": date(2000, 1, 1),
            "roles": ["USER"],
            "company_id": company.id,
        })
        assert user.id is not None
        assert user.email == "repo@test.com"

    def test_get_user_by_id(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="byid@test.com", company_id=company.id)
        repo = UserRepository(db_session)
        found = repo.get_by_id(user.id)
        assert found is not None
        assert found.email == "byid@test.com"

    def test_get_user_by_id_not_found(self, db_session):
        repo = UserRepository(db_session)
        assert repo.get_by_id(9999) is None

    def test_get_user_by_email(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="byemail@test.com", company_id=company.id)
        repo = UserRepository(db_session)
        found = repo.get_user_by_email("byemail@test.com")
        assert found is not None

    def test_get_user_by_email_not_found(self, db_session):
        repo = UserRepository(db_session)
        assert repo.get_user_by_email("nope@test.com") is None

    def test_get_user_by_username(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="byname@test.com", username="uniquename", company_id=company.id)
        repo = UserRepository(db_session)
        found = repo.get_user_by_username("uniquename")
        assert found is not None

    def test_get_user_by_username_none(self, db_session):
        repo = UserRepository(db_session)
        assert repo.get_user_by_username(None) is None

    def test_get_users_list(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="u1@test.com", username="user1", company_id=company.id)
        create_user(email="u2@test.com", username="user2", company_id=company.id)
        repo = UserRepository(db_session)
        users, total = repo.get_list(filters=UserFilters())
        assert total == 2

    def test_get_users_list_pagination(self, db_session, create_company, create_user):
        company = create_company()
        for i in range(5):
            create_user(email=f"u{i}@test.com", username=f"user{i}", company_id=company.id)
        repo = UserRepository(db_session)
        users, total = repo.get_list(filters=UserFilters(size=2))
        assert len(users) == 2
        assert total == 5

    def test_update_user(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="update@test.com", company_id=company.id)
        repo = UserRepository(db_session)
        updated = repo.update(user.id, {"first_name": "Updated"})
        assert updated.first_name == "Updated"

    def test_update_user_not_found(self, db_session):
        repo = UserRepository(db_session)
        assert repo.update(9999, {"first_name": "X"}) is None

    def test_delete_user(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="delete@test.com", company_id=company.id)
        repo = UserRepository(db_session)
        assert repo.delete_user(user.id) is True
        assert repo.get_by_id(user.id) is None

    def test_delete_user_not_found(self, db_session):
        repo = UserRepository(db_session)
        assert repo.delete_user(9999) is False

    def test_deactivate_user(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="deactivate@test.com", company_id=company.id)
        repo = UserRepository(db_session)
        deactivated = repo.soft_delete(user.id)
        assert deactivated.is_active is False


# ============================================
# USER SERVICE TESTS
# ============================================

class TestUserServiceCreate:

    def test_create_user_success(self, db_session, create_company):
        company = create_company()
        service = UserService(db_session)
        user_data = UserCreate(
            email="new@test.com",
            username="newuser",
            password="password123",
            first_name="New",
            last_name="User",
            phone_number="123456",
            date_of_birth=date(2000, 1, 1),
            roles=[UserRole.USER],
            company_id=company.id,
        )
        user = service.create(user_data)
        assert user.id is not None
        assert user.email == "new@test.com"
        # Password should be hashed
        assert user.hashed_password != "password123"

    def test_create_user_duplicate_email(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="dup@test.com", company_id=company.id)
        service = UserService(db_session)
        with pytest.raises(ConflictException) as exc_info:
            service.create(UserCreate(
                email="dup@test.com",
                username="different",
                password="password123",
                first_name="Dup",
                last_name="User",
                phone_number="123",
                date_of_birth=date(2000, 1, 1),
                company_id=company.id,
            ))
        assert "Email already registered" in str(exc_info.value)

    def test_create_user_duplicate_username(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="orig@test.com", username="taken", company_id=company.id)
        service = UserService(db_session)
        with pytest.raises(ConflictException) as exc_info:
            service.create(UserCreate(
                email="unique@test.com",
                username="taken",
                password="password123",
                first_name="Dup",
                last_name="User",
                phone_number="123",
                date_of_birth=date(2000, 1, 1),
                company_id=company.id,
            ))
        assert "Username already taken" in str(exc_info.value)


class TestUserServiceGet:

    def test_get_user_by_id(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="get@test.com", company_id=company.id)
        service = UserService(db_session)
        found = service.get_by_id(user.id)
        assert found is not None
        assert found.id == user.id

    def test_get_user_by_id_not_found(self, db_session):
        service = UserService(db_session)
        with pytest.raises(NotFoundException):
            service.get_by_id(9999)

    def test_get_user_by_email(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="getemail@test.com", company_id=company.id)
        service = UserService(db_session)
        found = service.get_user_by_email("getemail@test.com")
        assert found is not None

    def test_get_users_list(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="list1@test.com", username="lu1", company_id=company.id)
        create_user(email="list2@test.com", username="lu2", company_id=company.id)
        service = UserService(db_session)
        users, total = service.get_list(filters=UserFilters())
        assert total == 2


class TestUserServiceUpdate:

    def test_update_user_success(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="upd@test.com", company_id=company.id)
        service = UserService(db_session)
        updated = service.update(user.id, UserUpdate(first_name="Updated"))
        assert updated.first_name == "Updated"

    def test_update_user_not_found(self, db_session):
        service = UserService(db_session)
        with pytest.raises(NotFoundException):
            service.update(9999, UserUpdate(first_name="X"))

    def test_update_user_password_is_hashed(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="updpw@test.com", company_id=company.id)
        service = UserService(db_session)
        updated = service.update(user.id, UserUpdate(password="newpassword123"))
        assert updated.hashed_password != "newpassword123"

    def test_update_user_duplicate_email(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="existing@test.com", username="u1", company_id=company.id)
        user2 = create_user(email="other@test.com", username="u2", company_id=company.id)
        service = UserService(db_session)
        with pytest.raises(ConflictException):
            service.update(user2.id, UserUpdate(email="existing@test.com"))

    def test_update_user_empty_field_rejected(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="empty@test.com", company_id=company.id)
        service = UserService(db_session)
        with pytest.raises(BadRequestException):
            service.update(user.id, UserUpdate(first_name=""))


class TestUserServiceDelete:

    def test_delete_user(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="del@test.com", company_id=company.id)
        service = UserService(db_session)
        assert service.delete_user(user.id) is True

    def test_delete_user_not_found(self, db_session):
        service = UserService(db_session)
        assert service.delete_user(9999) is False

    def test_deactivate_user(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="deact@test.com", company_id=company.id)
        service = UserService(db_session)
        deactivated = service.soft_delete(user.id)
        assert deactivated.is_active is False


class TestUserServiceAuthenticate:

    def test_authenticate_success(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="auth@test.com", password="mypass", company_id=company.id)
        service = UserService(db_session)
        user = service.authenticate_user("auth@test.com", "mypass")
        assert user is not None

    def test_authenticate_wrong_password(self, db_session, create_company, create_user):
        company = create_company()
        create_user(email="auth@test.com", password="mypass", company_id=company.id)
        service = UserService(db_session)
        assert service.authenticate_user("auth@test.com", "wrong") is None

    def test_authenticate_inactive(self, db_session, create_company, create_user):
        company = create_company()
        create_user(
            email="auth@test.com",
            password="mypass",
            company_id=company.id,
            is_active=False,
        )
        service = UserService(db_session)
        assert service.authenticate_user("auth@test.com", "mypass") is None


class TestUserServicePassword:

    def test_hash_password(self):
        hashed = UserService.hash_password("testpass")
        assert hashed != "testpass"
        assert hashed.startswith("$2b$")

    def test_verify_password(self):
        hashed = UserService.hash_password("testpass")
        assert UserService.verify_password("testpass", hashed) is True
        assert UserService.verify_password("wrong", hashed) is False


# ============================================
# USER ROUTER / ENDPOINT TESTS
# ============================================

class TestCreateUserEndpoint:

    def test_create_user_via_api(self, client, db_session, create_company, super_admin_headers):
        company = create_company()
        headers, _ = super_admin_headers
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.post("/api/users/", json={
                "email": "api@test.com",
                "username": "apiuser",
                "password": "password123",
                "first_name": "API",
                "last_name": "User",
                "phone_number": "123456",
                "date_of_birth": "2000-01-01",
                "roles": ["USER"],
                "company_id": company.id,
            }, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == 201

        from app.features.users.users_models import User
        from app.features.wallet.wallet_model import Wallet, WalletOwnerType
        user = db_session.query(User).filter(User.email == "api@test.com").one()
        wallet = db_session.query(Wallet).filter(
            Wallet.owner_id == user.id, Wallet.owner_type == WalletOwnerType.USER
        ).one()
        assert user.w_id == wallet.id
        assert wallet.name == "API User"

    def test_create_user_missing_required_fields(self, client, super_admin_headers):
        headers, _ = super_admin_headers
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.post("/api/users/", json={
                "email": "incomplete@test.com",
            }, headers=headers)
        assert response.status_code == 422

    def test_create_user_missing_company_id(self, client, super_admin_headers):
        headers, _ = super_admin_headers
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.post("/api/users/", json={
                "email": "nocompany@test.com",
                "username": "nocompany",
                "password": "password123",
                "first_name": "No",
                "last_name": "Company",
                "phone_number": "123456",
                "date_of_birth": "2000-01-01",
                "roles": ["COACH"],
            }, headers=headers)
        assert response.status_code == 422

    def test_create_user_unknown_company_id(self, client, super_admin_headers):
        headers, _ = super_admin_headers
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.post("/api/users/", json={
                "email": "badcompany@test.com",
                "username": "badcompany",
                "password": "password123",
                "first_name": "Bad",
                "last_name": "Company",
                "phone_number": "123456",
                "date_of_birth": "2000-01-01",
                "roles": ["COACH"],
                "company_id": 999999,
            }, headers=headers)
        assert response.status_code == 400

    def test_create_user_invalid_email(self, client, super_admin_headers):
        headers, _ = super_admin_headers
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.post("/api/users/", json={
                "email": "not-an-email",
                "username": "test",
                "password": "password123",
                "first_name": "Test",
                "last_name": "User",
                "phone_number": "123",
                "date_of_birth": "2000-01-01",
            }, headers=headers)
        assert response.status_code == 422


def _call(client, method, url, headers, **kwargs):
    from unittest.mock import patch
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


class TestGetUsersEndpoint:

    def test_get_user_by_id_via_api(self, client, create_user, auth_headers):
        headers, _, company = auth_headers
        user = create_user(email="getapi@test.com", username="getapi", company_id=company.id)
        response = _call(client, "get", f"/api/users/{user.id}", headers)
        assert response.status_code == 200
        assert response.json()["data"]["email"] == "getapi@test.com"

    def test_get_user_not_found(self, client, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "get", "/api/users/99999", headers)
        assert response.status_code == 404

    def test_get_user_unauthenticated(self, client):
        response = client.get("/api/users/1")
        assert response.status_code in (401, 403)


class TestUsersCompanyScope:
    """Non-SUPER_ADMIN users only see and manage users of their own company."""

    def _other_company_user(self, create_company, create_user):
        other = create_company(name="Other Club")
        return other, create_user(email="other@test.com", username="other", company_id=other.id)

    def test_list_only_own_company(self, client, create_company, create_user, auth_headers):
        headers, admin, company = auth_headers
        create_user(email="mine@test.com", username="mine", company_id=company.id)
        self._other_company_user(create_company, create_user)

        response = _call(client, "get", "/api/users/", headers)
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert {i["company_id"] for i in items} == {company.id}
        assert "other@test.com" not in {i["email"] for i in items}

    def test_list_company_filter_cannot_widen_scope(self, client, create_company, create_user, auth_headers):
        headers, _, _ = auth_headers
        other, _ = self._other_company_user(create_company, create_user)

        response = _call(client, "get", f"/api/users/?company_id={other.id}", headers)
        assert response.status_code == 200
        assert response.json()["data"]["items"] == []

    def test_get_other_company_user_403(self, client, create_company, create_user, auth_headers):
        headers, _, _ = auth_headers
        _, other_user = self._other_company_user(create_company, create_user)

        response = _call(client, "get", f"/api/users/{other_user.id}", headers)
        assert response.status_code == 403

    def test_update_other_company_user_403(self, client, create_company, create_user, auth_headers):
        headers, _, _ = auth_headers
        _, other_user = self._other_company_user(create_company, create_user)

        response = _call(client, "put", f"/api/users/{other_user.id}", headers, json={"first_name": "Hacked"})
        assert response.status_code == 403

    def test_deactivate_other_company_user_403(self, client, create_company, create_user, auth_headers):
        headers, _, _ = auth_headers
        _, other_user = self._other_company_user(create_company, create_user)

        response = _call(client, "post", f"/api/users/{other_user.id}/deactivate", headers)
        assert response.status_code == 403

    def test_delete_other_company_user_403(self, client, db_session, create_company, create_user, auth_headers):
        headers, _, _ = auth_headers
        _, other_user = self._other_company_user(create_company, create_user)

        response = _call(client, "delete", f"/api/users/{other_user.id}", headers)
        assert response.status_code == 403
        assert db_session.get(User, other_user.id) is not None

    def test_create_user_in_other_company_403(self, client, create_company, auth_headers):
        headers, _, _ = auth_headers
        other = create_company(name="Other Club")

        response = _call(client, "post", "/api/users/", headers, json={
            "email": "new@test.com",
            "username": "newuser",
            "password": "password123",
            "first_name": "New",
            "last_name": "User",
            "phone_number": "123456",
            "date_of_birth": "2000-01-01",
            "roles": ["USER"],
            "company_id": other.id,
        })
        assert response.status_code == 403

    def test_super_admin_sees_all_companies(self, client, create_company, create_user, super_admin_headers):
        headers, admin = super_admin_headers
        _, other_user = self._other_company_user(create_company, create_user)

        response = _call(client, "get", "/api/users/", headers)
        assert response.status_code == 200
        company_ids = {i["company_id"] for i in response.json()["data"]["items"]}
        assert {admin.company_id, other_user.company_id} <= company_ids

        response = _call(client, "get", f"/api/users/{other_user.id}", headers)
        assert response.status_code == 200
