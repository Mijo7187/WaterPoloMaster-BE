# ============================================
# MEMBERSHIP TESTS
# ============================================

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.core.api.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
)
from app.features.membership.membership_model import Program, divides_term_evenly
from app.features.membership.membership_repository import MembershipRepository
from app.features.membership.membership_schemas import (
    MembershipCreate,
    MembershipFilters,
    MembershipUpdate,
)
from app.features.membership.membership_service import MembershipService


def _create(db_session, company, **kwargs):
    payload = dict(
        company_id=company.id,
        name="Senior Waterpolo",
        program=Program.WATERPOLO,
        months_count=1,
        price_month=Decimal("5000.00"),
        installments_count=1,
    )
    payload.update(kwargs)
    return MembershipService(db_session).create(MembershipCreate(**payload))


class TestDividesTermEvenly:

    @pytest.mark.parametrize("months,count", [(1, 1), (3, 1), (3, 3), (12, 4), (12, 6)])
    def test_even_splits(self, months, count):
        assert divides_term_evenly(months, count) is True

    @pytest.mark.parametrize("months,count", [(3, 2), (12, 5), (1, 2), (3, 0), (0, 1)])
    def test_uneven_splits(self, months, count):
        assert divides_term_evenly(months, count) is False


class TestMembershipRepository:

    def test_create_and_get(self, db_session, create_company):
        company = create_company()
        repo = MembershipRepository(db_session)
        row = repo.create({
            "company_id": company.id,
            "name": "U15 Swimming",
            "program": Program.SWIMMING,
            "months_count": 3,
            "price_month": Decimal("4000.00"),
            "installments_count": 3,
            "is_active": True,
        })
        assert row.id is not None
        assert repo.get_by_id(row.id).name == "U15 Swimming"

    def test_filter_by_program(self, db_session, create_company):
        company = create_company()
        _create(db_session, company, name="Polo", program=Program.WATERPOLO)
        _create(db_session, company, name="Swim", program=Program.SWIMMING)

        items, total = MembershipRepository(db_session).get_list(
            filters=MembershipFilters(program=Program.SWIMMING)
        )
        assert total == 1
        assert items[0].name == "Swim"

    def test_filter_by_company(self, db_session, create_company):
        club_a = create_company(name="Club A")
        club_b = create_company(name="Club B")
        _create(db_session, club_a)
        _create(db_session, club_b)

        items, total = MembershipRepository(db_session).get_list(
            filters=MembershipFilters(company_id=club_b.id)
        )
        assert total == 1
        assert items[0].company_id == club_b.id

    def test_inactive_plans_can_be_filtered_out(self, db_session, create_company):
        company = create_company()
        _create(db_session, company, name="Current")
        _create(db_session, company, name="Retired", is_active=False)

        items, total = MembershipRepository(db_session).get_list(
            filters=MembershipFilters(is_active=True)
        )
        assert total == 1
        assert items[0].name == "Current"


class TestMembershipService:

    def test_uneven_installment_split_is_rejected(self, db_session, create_company):
        """2 installments over a 3-month term would be 1.5 months each."""
        company = create_company()
        with pytest.raises(BadRequestException, match="divide the 3-month term"):
            _create(db_session, company, months_count=3, installments_count=2)

    def test_duplicate_name_and_program_is_rejected(self, db_session, create_company):
        company = create_company()
        _create(db_session, company, name="Senior", program=Program.WATERPOLO)
        with pytest.raises(ConflictException, match="already has a membership"):
            _create(db_session, company, name="Senior", program=Program.WATERPOLO)

    def test_same_name_in_another_program_is_allowed(self, db_session, create_company):
        company = create_company()
        _create(db_session, company, name="Senior", program=Program.WATERPOLO)
        other = _create(db_session, company, name="Senior", program=Program.SWIMMING)
        assert other.id is not None

    def test_same_name_in_another_company_is_allowed(self, db_session, create_company):
        club_a = create_company(name="Club A")
        club_b = create_company(name="Club B")
        _create(db_session, club_a, name="Senior")
        other = _create(db_session, club_b, name="Senior")
        assert other.id is not None

    def test_update_into_an_existing_name_is_rejected(self, db_session, create_company):
        """The gap offering_price had: uniqueness was only checked on create,
        so a rename surfaced a raw IntegrityError instead of a 409."""
        company = create_company()
        _create(db_session, company, name="Senior", program=Program.WATERPOLO)
        second = _create(db_session, company, name="Junior", program=Program.WATERPOLO)

        with pytest.raises(ConflictException, match="already has a membership"):
            MembershipService(db_session).update(
                second.id, MembershipUpdate(name="Senior")
            )

    def test_updating_a_row_to_its_own_values_is_allowed(self, db_session, create_company):
        company = create_company()
        row = _create(db_session, company, name="Senior")
        updated = MembershipService(db_session).update(
            row.id, MembershipUpdate(name="Senior", price_month=Decimal("6000.00"))
        )
        assert updated.price_month == Decimal("6000.00")

    def test_update_validates_the_split_against_the_existing_row(
        self, db_session, create_company
    ):
        """months_count comes from the stored row when only the count changes."""
        company = create_company()
        row = _create(db_session, company, months_count=3, installments_count=3)

        with pytest.raises(BadRequestException, match="divide the 3-month term"):
            MembershipService(db_session).update(
                row.id, MembershipUpdate(installments_count=2)
            )

    def test_admin_cannot_edit_another_companys_membership(
        self, db_session, create_company, create_user
    ):
        club_a = create_company(name="Club A")
        club_b = create_company(name="Club B")
        row = _create(db_session, club_a)
        outsider = create_user(company_id=club_b.id)

        with pytest.raises(ForbiddenException, match="your own company"):
            MembershipService(db_session).update(
                row.id, MembershipUpdate(price_month=Decimal("1.00")),
                current_user=outsider,
            )

    def test_delete_removes_the_row(self, db_session, create_company):
        company = create_company()
        row = _create(db_session, company)
        MembershipService(db_session).delete(row.id)
        assert MembershipRepository(db_session).get_by_id(row.id) is None


class TestMembershipEndpoints:

    def test_create_and_list_endpoint(self, client, db_session, auth_headers):
        headers, user, company = auth_headers
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            resp = client.post("/api/membership/", json={
                "company_id": company.id,
                "name": "Senior Waterpolo",
                "program": "waterpolo",
                "months_count": 3,
                "price_month": "5000.00",
                "installments_count": 3,
            }, headers=headers)
            # create returns just the new id: data is [id]
            assert resp.status_code == 201, resp.text
            item_id = list(resp.json()["data"])[0]

            listed = client.get("/api/membership/", headers=headers)
            assert listed.status_code == 200
            items = listed.json()["data"]["items"]
            assert isinstance(items, list)
            # The term total is computed, not stored.
            assert Decimal(str(items[0]["price_total"])) == Decimal("15000.00")

            one = client.get(f"/api/membership/{item_id}", headers=headers)
            assert one.status_code == 200
            assert Decimal(str(one.json()["data"]["price_total"])) == Decimal("15000.00")

    def test_uneven_split_returns_400(self, client, db_session, auth_headers):
        headers, user, company = auth_headers
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            resp = client.post("/api/membership/", json={
                "company_id": company.id,
                "name": "Bad Split",
                "program": "waterpolo",
                "months_count": 3,
                "price_month": "5000.00",
                "installments_count": 2,
            }, headers=headers)
            assert resp.status_code == 400, resp.text

    def test_duplicate_returns_409(self, client, db_session, auth_headers):
        headers, user, company = auth_headers
        body = {
            "company_id": company.id,
            "name": "Dup",
            "program": "waterpolo",
            "months_count": 1,
            "price_month": "5000.00",
            "installments_count": 1,
        }
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            assert client.post("/api/membership/", json=body, headers=headers).status_code == 201
            second = client.post("/api/membership/", json=body, headers=headers)
            assert second.status_code == 409, second.text

    def test_delete_endpoint(self, client, db_session, auth_headers, create_company):
        headers, user, company = auth_headers
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            created = client.post("/api/membership/", json={
                "company_id": company.id,
                "name": "Doomed",
                "program": "swimming",
                "months_count": 1,
                "price_month": "1000.00",
                "installments_count": 1,
            }, headers=headers)
            item_id = list(created.json()["data"])[0]

            resp = client.delete(f"/api/membership/{item_id}", headers=headers)
            assert resp.status_code == 200, resp.text


def _call(client, method, url, headers, **kwargs):
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


class TestMembershipCompanyScope:
    """Non-SUPER_ADMIN users only see and manage memberships of their own company."""

    @pytest.fixture()
    def other_membership(self, db_session, create_company):
        return _create(db_session, create_company(name="Other Club"), name="Other Plan")

    def test_list_excludes_other_company(self, client, other_membership, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "get", "/api/membership/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert other_membership.id not in ids

    def test_get_other_company_membership_403(self, client, other_membership, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "get", f"/api/membership/{other_membership.id}", headers)
        assert response.status_code == 403

    def test_update_other_company_membership_403(self, client, other_membership, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "put", f"/api/membership/{other_membership.id}", headers,
                         json={"name": "Hijacked"})
        assert response.status_code == 403

    def test_delete_other_company_membership_403(
        self, client, db_session, other_membership, auth_headers
    ):
        headers, _, _ = auth_headers
        response = _call(client, "delete", f"/api/membership/{other_membership.id}", headers)
        assert response.status_code == 403
        assert MembershipRepository(db_session).get_by_id(other_membership.id) is not None

    def test_create_membership_in_other_company_403(self, client, create_company, auth_headers):
        headers, _, _ = auth_headers
        other = create_company(name="Other Club")
        response = _call(client, "post", "/api/membership/", headers, json={
            "company_id": other.id,
            "name": "Sneaky",
            "program": "waterpolo",
            "months_count": 1,
            "price_month": "1000.00",
            "installments_count": 1,
        })
        assert response.status_code == 403

    def test_super_admin_sees_other_company_membership(
        self, client, other_membership, super_admin_headers
    ):
        headers, _ = super_admin_headers
        response = _call(client, "get", f"/api/membership/{other_membership.id}", headers)
        assert response.status_code == 200
