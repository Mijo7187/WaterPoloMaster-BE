# ============================================
# COMPANY TESTS
# ============================================

import pytest

from app.features.company.company_service import CompanyService
from app.features.company.company_repository import CompanyRepository
from app.features.company.company_schemas import CompanyCreate, CompanyFilters, CompanyUpdate
from app.features.company.company_model import CompanyType
from app.core.api.exceptions import NotFoundException


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
