# ============================================
# COMPANY TESTS
# ============================================

import pytest

from app.features.company.company_service import CompanyService
from app.features.company.company_repository import CompanyRepository
from app.features.company.company_schemas import CompanyCreate, CompanyFilters, CompanyUpdate
from app.features.company.company_model import CompanyType
from app.core.api.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)


# ============================================
# COMPANY REPOSITORY TESTS
# ============================================

class TestCompanyRepository:

    def test_create_company(self, db_session):
        repo = CompanyRepository(db_session)
        company = repo.create({"name": "WP Club", "city": "Belgrade"})
        assert company.id is not None
        assert company.name == "WP Club"

    def test_get_by_id(self, db_session, create_company):
        company = create_company(name="FindMe")
        repo = CompanyRepository(db_session)
        found = repo.get_by_id(company.id)
        assert found is not None
        assert found.name == "FindMe"

    def test_get_by_id_not_found(self, db_session):
        repo = CompanyRepository(db_session)
        assert repo.get_by_id(9999) is None

    def test_get_list(self, db_session, create_company):
        create_company(name="Club A")
        create_company(name="Club B")
        repo = CompanyRepository(db_session)
        items, total = repo.get_list(filters=CompanyFilters())
        assert total == 2

    def test_get_list_pagination(self, db_session, create_company):
        for i in range(5):
            create_company(name=f"Club {i}")
        repo = CompanyRepository(db_session)
        items, total = repo.get_list(filters=CompanyFilters(size=2))
        assert len(items) == 2
        assert total == 5

    def test_update_company(self, db_session, create_company):
        company = create_company(name="Old Name")
        repo = CompanyRepository(db_session)
        updated = repo.update(company.id, {"name": "New Name"})
        assert updated.name == "New Name"

    def test_update_company_not_found(self, db_session):
        repo = CompanyRepository(db_session)
        assert repo.update(9999, {"name": "X"}) is None


# ============================================
# COMPANY SERVICE TESTS
# ============================================

class TestCompanyServiceCreate:

    def test_create_company(self, db_session):
        service = CompanyService(db_session)
        company = service.create(CompanyCreate(
            name="New Club",
            address="123 Main St",
            city_id=1,
            country_id=1,
            phone_number="+381111",
            email="club@test.com",
            company_type=CompanyType.CLUB,
        ))
        assert company.id is not None
        assert company.name == "New Club"

    def test_create_company_with_all_fields(self, db_session):
        service = CompanyService(db_session)
        company = service.create(CompanyCreate(
            name="Full Club",
            address="123 Main St",
            city_id=1,
            country_id=1,
            phone_number="+381111",
            email="club@test.com",
            company_type=CompanyType.POOL,
        ))
        assert company.email == "club@test.com"
        assert company.company_type == CompanyType.POOL.value


class TestCompanyServiceGet:

    def test_get_by_id(self, db_session, create_company):
        company = create_company(name="Get Club")
        service = CompanyService(db_session)
        found = service.get_by_id(company.id)
        assert found.name == "Get Club"

    def test_get_by_id_not_found(self, db_session):
        service = CompanyService(db_session)
        with pytest.raises(NotFoundException):
            service.get_by_id(9999)

    def test_get_list(self, db_session, create_company):
        create_company(name="A")
        create_company(name="B")
        service = CompanyService(db_session)
        items, total = service.get_list(filters=CompanyFilters())
        assert total == 2


class TestCompanyServiceUpdate:

    def test_update_company(self, db_session, create_company):
        company = create_company(name="Old")
        service = CompanyService(db_session)
        updated = service.update(company.id, CompanyUpdate(name="Updated"))
        assert updated.name == "Updated"

    def test_update_company_not_found(self, db_session):
        service = CompanyService(db_session)
        with pytest.raises(NotFoundException):
            service.update(9999, CompanyUpdate(name="X"))

    def test_update_partial(self, db_session, create_company):
        company = create_company(name="Club", phone_number="111")
        service = CompanyService(db_session)
        updated = service.update(company.id, CompanyUpdate(phone_number="222"))
        assert updated.phone_number == "222"
        assert updated.name == "Club"  # unchanged


# ============================================
# COMPANY ROUTER / ENDPOINT TESTS
# ============================================

class TestCompanyEndpoints:

    def test_create_company_endpoint(self, client, super_admin_headers):
        headers, user = super_admin_headers
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.post("/api/company/", json={
                "name": "API Club",
                "address": "1 Main St",
                "city_id": 1,
                "country_id": 1,
                "phone_number": "+381111",
                "email": "apiclub@test.com",
                "company_type": "CLUB",
            }, headers=headers)
            assert response.status_code == 201

    def test_get_companies_endpoint(self, client, db_session, create_company, super_admin_headers):
        create_company(name="C1")
        create_company(name="C2")
        headers, user = super_admin_headers
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.get("/api/company/", headers=headers)
            assert response.status_code == 200
            assert len(response.json()["data"]["items"]) >= 2

    def test_get_company_by_id_endpoint(self, client, db_session, create_company, super_admin_headers):
        company = create_company(name="FindAPI")
        headers, user = super_admin_headers
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.get(f"/api/company/{company.id}", headers=headers)
            assert response.status_code == 200
            assert response.json()["data"]["name"] == "FindAPI"

    def test_update_company_endpoint(self, client, db_session, create_company, super_admin_headers):
        company = create_company(name="Before")
        headers, user = super_admin_headers
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.put(
                f"/api/company/{company.id}",
                json={"name": "After"},
                headers=headers,
            )
            assert response.status_code == 200
            assert response.json()["data"]["name"] == "After"

    def test_create_company_unauthenticated(self, client):
        response = client.post("/api/company/", json={"name": "NoAuth Club"})
        assert response.status_code in (401, 403)


# ============================================
# COMPANY SCOPE
# ============================================

def _call(client, method, url, headers, **kwargs):
    from unittest.mock import patch

    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


class TestCompanyCompanyScope:
    """
    A non-SUPER_ADMIN sees their own company plus every POOL and SUPPLIER —
    pools are picked by id on trainings and tournaments. Other CLUBs are hidden,
    and a visible pool still cannot be edited.
    """

    @pytest.fixture()
    def coach_headers(self, create_company, create_user, mock_redis):
        from app.core.security import create_access_token
        from app.features.users.users_models import UserRole

        company = create_company(name="Coach Club")
        user = create_user(
            email="coach@test.com",
            username="coach",
            roles=[UserRole.COACH],
            company_id=company.id,
        )
        token = create_access_token({
            "sub": user.email,
            "user_id": user.id,
            "roles": user.roles,
            "type": "access",
        })
        mock_redis["store_access_token"](user.id, token)
        return {"Authorization": f"Bearer {token}"}, user, company

    def test_list_hides_other_clubs_but_keeps_pools_and_suppliers(
        self, client, create_company, auth_headers
    ):
        headers, _, company = auth_headers
        other_club = create_company(name="Other Club", company_type=CompanyType.CLUB.value)
        pool = create_company(name="City Pool", company_type=CompanyType.POOL.value)
        supplier = create_company(name="Kit Supplier", company_type=CompanyType.SUPPLIER.value)

        response = _call(client, "get", "/api/company/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert company.id in ids
        assert pool.id in ids
        assert supplier.id in ids
        assert other_club.id not in ids

    def test_get_pool_by_id_allowed(self, client, create_company, auth_headers):
        headers, _, _ = auth_headers
        pool = create_company(name="City Pool", company_type=CompanyType.POOL.value)

        response = _call(client, "get", f"/api/company/{pool.id}", headers)
        assert response.status_code == 200

    def test_get_other_club_403(self, client, create_company, auth_headers):
        headers, _, _ = auth_headers
        other_club = create_company(name="Other Club", company_type=CompanyType.CLUB.value)

        response = _call(client, "get", f"/api/company/{other_club.id}", headers)
        assert response.status_code == 403

    def test_update_pool_forbidden_even_though_visible(
        self, client, create_company, auth_headers
    ):
        """Readable is not writable — writes ignore the pool/supplier carve-out."""
        headers, _, _ = auth_headers
        pool = create_company(name="City Pool", company_type=CompanyType.POOL.value)

        response = _call(client, "put", f"/api/company/{pool.id}", headers,
                         json={"name": "Hijacked"})
        assert response.status_code == 403

    def test_update_own_company_allowed(self, client, auth_headers):
        headers, _, company = auth_headers
        response = _call(client, "put", f"/api/company/{company.id}", headers,
                         json={"name": "Renamed"})
        assert response.status_code == 200

    def test_super_admin_sees_every_club(self, client, create_company, super_admin_headers):
        headers, _ = super_admin_headers
        other_club = create_company(name="Other Club", company_type=CompanyType.CLUB.value)

        response = _call(client, "get", "/api/company/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert other_club.id in ids

    def test_coach_can_list_companies(self, client, create_company, coach_headers):
        """COACH needs the pool list to create a training."""
        headers, _, company = coach_headers
        pool = create_company(name="City Pool", company_type=CompanyType.POOL.value)

        response = _call(client, "get", "/api/company/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert {company.id, pool.id} <= ids


# ============================================
# ACADEMY MEMBERSHIP
# ============================================

class TestAcademyMembershipService:

    def test_add_company_to_academy(self, db_session, create_company):
        academy = create_company(name="Academy", company_type=CompanyType.ACADEMY.value)
        club = create_company(name="Club", company_type=CompanyType.CLUB.value)
        service = CompanyService(db_session)

        updated = service.add_company_to_academy(academy.id, club.id)
        assert updated.academy_id == academy.id
        assert updated.academy.name == "Academy"

    def test_remove_company_from_academy(self, db_session, create_company):
        academy = create_company(name="Academy", company_type=CompanyType.ACADEMY.value)
        club = create_company(name="Club", company_type=CompanyType.CLUB.value)
        service = CompanyService(db_session)
        service.add_company_to_academy(academy.id, club.id)

        updated = service.remove_company_from_academy(academy.id, club.id)
        assert updated.academy_id is None
        assert updated.academy is None

    def test_list_academy_members(self, db_session, create_company):
        academy = create_company(name="Academy", company_type=CompanyType.ACADEMY.value)
        inside = create_company(name="Inside", company_type=CompanyType.CLUB.value)
        create_company(name="Outside", company_type=CompanyType.CLUB.value)
        service = CompanyService(db_session)
        service.add_company_to_academy(academy.id, inside.id)

        items, total = service.get_academy_members(academy.id, CompanyFilters())
        assert total == 1
        assert [i.id for i in items] == [inside.id]

    def test_list_ignores_client_sent_academy_id(self, db_session, create_company):
        """The path academy_id wins — a client filter cannot widen the result."""
        academy = create_company(name="Academy", company_type=CompanyType.ACADEMY.value)
        other = create_company(name="Other Academy", company_type=CompanyType.ACADEMY.value)
        inside = create_company(name="Inside", company_type=CompanyType.CLUB.value)
        service = CompanyService(db_session)
        service.add_company_to_academy(academy.id, inside.id)

        items, total = service.get_academy_members(
            academy.id, CompanyFilters(academy_id=other.id)
        )
        assert total == 1
        assert items[0].id == inside.id

    def test_academy_not_found(self, db_session, create_company):
        club = create_company(name="Club", company_type=CompanyType.CLUB.value)
        service = CompanyService(db_session)
        with pytest.raises(NotFoundException):
            service.add_company_to_academy(9999, club.id)

    def test_target_must_be_an_academy(self, db_session, create_company):
        not_academy = create_company(name="Just a club", company_type=CompanyType.CLUB.value)
        club = create_company(name="Club", company_type=CompanyType.CLUB.value)
        service = CompanyService(db_session)
        with pytest.raises(BadRequestException):
            service.add_company_to_academy(not_academy.id, club.id)

    def test_academy_cannot_join_an_academy(self, db_session, create_company):
        academy = create_company(name="Academy", company_type=CompanyType.ACADEMY.value)
        other = create_company(name="Other Academy", company_type=CompanyType.ACADEMY.value)
        service = CompanyService(db_session)
        with pytest.raises(BadRequestException):
            service.add_company_to_academy(academy.id, other.id)

    def test_academy_cannot_contain_itself(self, db_session, create_company):
        academy = create_company(name="Academy", company_type=CompanyType.ACADEMY.value)
        service = CompanyService(db_session)
        with pytest.raises(BadRequestException):
            service.add_company_to_academy(academy.id, academy.id)

    def test_company_already_in_another_academy(self, db_session, create_company):
        first = create_company(name="First", company_type=CompanyType.ACADEMY.value)
        second = create_company(name="Second", company_type=CompanyType.ACADEMY.value)
        club = create_company(name="Club", company_type=CompanyType.CLUB.value)
        service = CompanyService(db_session)
        service.add_company_to_academy(first.id, club.id)

        with pytest.raises(ConflictException):
            service.add_company_to_academy(second.id, club.id)

    def test_remove_from_wrong_academy(self, db_session, create_company):
        academy = create_company(name="Academy", company_type=CompanyType.ACADEMY.value)
        other = create_company(name="Other Academy", company_type=CompanyType.ACADEMY.value)
        club = create_company(name="Club", company_type=CompanyType.CLUB.value)
        service = CompanyService(db_session)
        service.add_company_to_academy(academy.id, club.id)

        with pytest.raises(NotFoundException):
            service.remove_company_from_academy(other.id, club.id)


class TestAcademyMembershipEndpoints:

    def test_super_admin_full_flow(self, client, create_company, super_admin_headers):
        headers, _ = super_admin_headers
        academy = create_company(name="Academy", company_type=CompanyType.ACADEMY.value)
        club = create_company(name="Club", company_type=CompanyType.CLUB.value)

        add = _call(client, "post", f"/api/academy/{academy.id}/companies", headers,
                    json={"company_id": club.id})
        assert add.status_code == 201
        assert add.json()["data"]["academy_id"] == academy.id

        listed = _call(client, "get", f"/api/academy/{academy.id}/companies", headers)
        assert listed.status_code == 200
        assert [i["id"] for i in listed.json()["data"]["items"]] == [club.id]

        removed = _call(client, "delete",
                        f"/api/academy/{academy.id}/companies/{club.id}", headers)
        assert removed.status_code == 200
        assert removed.json()["data"]["academy_id"] is None

        empty = _call(client, "get", f"/api/academy/{academy.id}/companies", headers)
        assert empty.json()["data"]["pagination"]["total"] == 0

    def test_company_get_by_id_exposes_academy(self, client, create_company, super_admin_headers):
        headers, _ = super_admin_headers
        academy = create_company(name="Academy", company_type=CompanyType.ACADEMY.value)
        club = create_company(name="Club", company_type=CompanyType.CLUB.value)
        _call(client, "post", f"/api/academy/{academy.id}/companies", headers,
              json={"company_id": club.id})

        response = _call(client, "get", f"/api/company/{club.id}", headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["academy_id"] == academy.id
        assert data["academy"]["name"] == "Academy"

    def test_company_without_academy_is_null(self, client, create_company, super_admin_headers):
        headers, _ = super_admin_headers
        club = create_company(name="Lone Club", company_type=CompanyType.CLUB.value)

        response = _call(client, "get", f"/api/company/{club.id}", headers)
        data = response.json()["data"]
        assert data["academy_id"] is None
        assert data["academy"] is None

    def test_admin_forbidden(self, client, create_company, auth_headers):
        """Academy membership is SUPER_ADMIN only."""
        headers, _, _ = auth_headers
        academy = create_company(name="Academy", company_type=CompanyType.ACADEMY.value)
        club = create_company(name="Club", company_type=CompanyType.CLUB.value)

        assert _call(client, "get", f"/api/academy/{academy.id}/companies",
                     headers).status_code == 403
        assert _call(client, "post", f"/api/academy/{academy.id}/companies", headers,
                     json={"company_id": club.id}).status_code == 403
        assert _call(client, "delete", f"/api/academy/{academy.id}/companies/{club.id}",
                     headers).status_code == 403
