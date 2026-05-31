import pytest

from app.common.crud.crud_schemas import CrudFilters
from app.core.api.exceptions import NotFoundException
from app.features.company.company_model import CompanyType
from app.features.company.company_repository import CompanyRepository
from app.features.company.company_schemas import CompanyCreate, CompanyUpdate
from app.features.company.company_service import CompanyService


# Minimal valid CompanyCreate payload for service-level tests.
# city_id / country_id are FK refs; SQLite won't enforce them in tests.
def _company_payload(**overrides) -> CompanyCreate:
    defaults = dict(
        name="Test Club",
        address="Test Street 1",
        city_id=1,
        country_id=1,
        phone_number="123456",
        email="club@test.com",
        company_type=CompanyType.CLUB,
    )
    defaults.update(overrides)
    return CompanyCreate(**defaults)


class TestCompanyRepository:

    def test_create_company(self, db_session):
        repo = CompanyRepository(db_session)
        company = repo.create({"name": "WP Club"})
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
        items, _ = repo.get_list(CrudFilters())
        assert len(items) == 2

    def test_get_list_pagination(self, db_session, create_company):
        for i in range(5):
            create_company(name=f"Club {i}")
        repo = CompanyRepository(db_session)
        items, _ = repo.get_list(CrudFilters(size=2))
        assert len(items) == 2

    def test_update_company(self, db_session, create_company):
        company = create_company(name="Old Name")
        repo = CompanyRepository(db_session)
        updated = repo.update(company.id, {"name": "New Name"})
        assert updated.name == "New Name"

    def test_update_company_not_found(self, db_session):
        repo = CompanyRepository(db_session)
        assert repo.update(9999, {"name": "X"}) is None


class TestCompanyServiceCreate:

    def test_create_company(self, db_session):
        service = CompanyService(db_session)
        company = service.create(_company_payload(name="New Club"))
        assert company.id is not None
        assert company.name == "New Club"

    def test_create_company_with_all_fields(self, db_session):
        service = CompanyService(db_session)
        company = service.create(_company_payload(
            name="Full Club",
            address="123 Main St",
            city_id=1,
            country_id=1,
            phone_number="+381111",
            email="full@test.com",
        ))
        assert company.city_id == 1
        assert company.email == "full@test.com"


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
        items, _ = service.get_list(CrudFilters())
        assert len(items) == 2


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
        company = create_company(name="Club")
        service = CompanyService(db_session)
        updated = service.update(company.id, CompanyUpdate(name="Updated Club"))
        assert updated.name == "Updated Club"


class TestCompanyEndpoints:

    def test_create_company_endpoint(self, client, super_admin_headers):
        headers, user, company = super_admin_headers
        response = client.post("/api/company/", json={
            "name": "API Club",
            "address": "Test St 1",
            "city_id": 1,
            "country_id": 1,
            "phone_number": "123456",
            "email": "api@club.com",
            "company_type": "CLUB",
        }, headers=headers)
        assert response.status_code == 201

    def test_get_companies_endpoint(self, client, db_session, create_company, super_admin_headers):
        headers, user, _ = super_admin_headers
        create_company(name="C1")
        create_company(name="C2")
        response = client.get("/api/company/", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["data"]["items"]) >= 2

    def test_get_company_by_id_endpoint(self, client, db_session, create_company, super_admin_headers):
        headers, user, _ = super_admin_headers
        company = create_company(name="FindAPI")
        response = client.get(f"/api/company/{company.id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "FindAPI"

    def test_update_company_endpoint(self, client, db_session, create_company, super_admin_headers):
        headers, user, _ = super_admin_headers
        company = create_company(name="Before")
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
