# ============================================
# MEMBERSHIP TESTS
# ============================================

from decimal import Decimal
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.api.exceptions import (
    ConflictException,
    ForbiddenException,
    ValidationException,
)
from app.features.membership.membership_model import BillingType, Program
from app.features.membership.membership_repository import MembershipRepository
from app.features.membership.membership_schemas import (
    MembershipCreate,
    MembershipFilters,
    MembershipUpdate,
)
from app.features.membership.membership_service import MembershipService
from app.features.sifarnici.selection.selection_model import Selection


@pytest.fixture()
def create_selection(db_session):
    def _create(company_id, name="U15", **kwargs):
        selection = Selection(company_id=company_id, name=name, **kwargs)
        db_session.add(selection)
        db_session.commit()
        db_session.refresh(selection)
        return selection
    return _create


def _create(db_session, company, selection, **kwargs):
    payload = dict(
        company_id=company.id,
        selection_id=selection.id,
        name="Senior Waterpolo",
        program=Program.WATERPOLO,
        billing_type=BillingType.MONTHLY,
        price=Decimal("5000.00"),
    )
    payload.update(kwargs)
    return MembershipService(db_session).create(MembershipCreate(**payload))


class TestBillingTypeValidation:
    """TERM needs a block length; MONTHLY must not carry one."""

    def test_term_requires_term_months(self, create_company, create_selection):
        company = create_company()
        with pytest.raises(ValidationError, match="term_months is required"):
            MembershipCreate(
                company_id=company.id,
                selection_id=create_selection(company_id=company.id).id,
                program=Program.WATERPOLO,
                billing_type=BillingType.TERM,
                price=Decimal("15000.00"),
            )

    def test_monthly_rejects_term_months(self, create_company, create_selection):
        company = create_company()
        with pytest.raises(ValidationError, match="must be null"):
            MembershipCreate(
                company_id=company.id,
                selection_id=create_selection(company_id=company.id).id,
                program=Program.WATERPOLO,
                billing_type=BillingType.MONTHLY,
                price=Decimal("5000.00"),
                term_months=3,
            )

    def test_term_with_months_is_accepted(self, db_session, create_company, create_selection):
        company = create_company()
        row = _create(
            db_session, company, create_selection(company_id=company.id),
            billing_type=BillingType.TERM, price=Decimal("15000.00"), term_months=3,
        )
        assert row.term_months == 3
        assert row.price == Decimal("15000.00")

    def test_switching_to_term_without_months_is_rejected(self):
        """Switching to TERM must bring a block length with it."""
        with pytest.raises(ValidationError, match="term_months is required"):
            MembershipUpdate(billing_type=BillingType.TERM)

    def test_switching_to_monthly_clears_term_months(
        self, db_session, create_company, create_selection
    ):
        """The leftover block length is dropped rather than rejected — the
        caller never sent it, and a MONTHLY plan has no term."""
        company = create_company()
        row = _create(
            db_session, company, create_selection(company_id=company.id),
            billing_type=BillingType.TERM, price=Decimal("15000.00"), term_months=3,
        )

        updated = MembershipService(db_session).update(
            row.id, MembershipUpdate(billing_type=BillingType.MONTHLY,
                                     price=Decimal("5000.00"))
        )
        assert updated.term_months is None


class TestMembershipRepository:

    def test_create_and_get(self, db_session, create_company, create_selection):
        company = create_company()
        selection = create_selection(company_id=company.id)
        repo = MembershipRepository(db_session)
        row = repo.create({
            "company_id": company.id,
            "selection_id": selection.id,
            "name": "U15 Swimming",
            "program": Program.SWIMMING,
            "billing_type": BillingType.MONTHLY,
            "price": Decimal("4000.00"),
            "is_active": True,
        })
        assert row.id is not None
        assert repo.get_by_id(row.id).name == "U15 Swimming"

    def test_filter_by_program(self, db_session, create_company, create_selection):
        company = create_company()
        selection = create_selection(company_id=company.id)
        _create(db_session, company, selection, name="Polo", program=Program.WATERPOLO)
        _create(db_session, company, selection, name="Swim", program=Program.SWIMMING)

        items, total = MembershipRepository(db_session).get_list(
            filters=MembershipFilters(program=Program.SWIMMING)
        )
        assert total == 1
        assert items[0].name == "Swim"

    def test_filter_by_selection(self, db_session, create_company, create_selection):
        company = create_company()
        u15 = create_selection(company_id=company.id, name="U15")
        masters = create_selection(company_id=company.id, name="Masters")
        _create(db_session, company, u15, name="U15 plan")
        _create(db_session, company, masters, name="Masters plan")

        items, total = MembershipRepository(db_session).get_list(
            filters=MembershipFilters(selection_id=masters.id)
        )
        assert total == 1
        assert items[0].name == "Masters plan"

    def test_filter_by_billing_type(self, db_session, create_company, create_selection):
        company = create_company()
        u15 = create_selection(company_id=company.id, name="U15")
        masters = create_selection(company_id=company.id, name="Masters")
        _create(db_session, company, u15)
        _create(db_session, company, masters, billing_type=BillingType.TERM,
                price=Decimal("15000.00"), term_months=3)

        items, total = MembershipRepository(db_session).get_list(
            filters=MembershipFilters(billing_type=BillingType.TERM)
        )
        assert total == 1
        assert items[0].term_months == 3

    def test_filter_by_company(self, db_session, create_company, create_selection):
        club_a = create_company(name="Club A")
        club_b = create_company(name="Club B")
        _create(db_session, club_a, create_selection(company_id=club_a.id))
        _create(db_session, club_b, create_selection(company_id=club_b.id))

        items, total = MembershipRepository(db_session).get_list(
            filters=MembershipFilters(company_id=club_b.id)
        )
        assert total == 1
        assert items[0].company_id == club_b.id

    def test_inactive_plans_can_be_filtered_out(
        self, db_session, create_company, create_selection
    ):
        company = create_company()
        u15 = create_selection(company_id=company.id, name="U15")
        masters = create_selection(company_id=company.id, name="Masters")
        _create(db_session, company, u15, name="Current")
        _create(db_session, company, masters, name="Retired", is_active=False)

        items, total = MembershipRepository(db_session).get_list(
            filters=MembershipFilters(is_active=True)
        )
        assert total == 1
        assert items[0].name == "Current"


class TestMembershipService:
    """The catalog key is (company, selection, program, billing_type).
    `name` is a free-text label and is deliberately NOT part of it."""

    def test_duplicate_catalog_key_is_rejected(
        self, db_session, create_company, create_selection
    ):
        company = create_company()
        selection = create_selection(company_id=company.id)
        _create(db_session, company, selection, name="Senior")
        with pytest.raises(ConflictException, match="already has a membership"):
            _create(db_session, company, selection, name="A different label")

    def test_same_selection_in_another_program_is_allowed(
        self, db_session, create_company, create_selection
    ):
        company = create_company()
        selection = create_selection(company_id=company.id)
        _create(db_session, company, selection, program=Program.WATERPOLO)
        other = _create(db_session, company, selection, program=Program.SWIMMING)
        assert other.id is not None

    def test_same_selection_with_another_billing_type_is_allowed(
        self, db_session, create_company, create_selection
    ):
        """A club may sell both a monthly and a block plan for one squad."""
        company = create_company()
        selection = create_selection(company_id=company.id)
        _create(db_session, company, selection)
        other = _create(db_session, company, selection,
                        billing_type=BillingType.TERM,
                        price=Decimal("15000.00"), term_months=3)
        assert other.id is not None

    def test_another_selection_is_allowed(
        self, db_session, create_company, create_selection
    ):
        company = create_company()
        _create(db_session, company, create_selection(company_id=company.id, name="U15"))
        other = _create(
            db_session, company, create_selection(company_id=company.id, name="U17")
        )
        assert other.id is not None

    def test_same_key_in_another_company_is_allowed(
        self, db_session, create_company, create_selection
    ):
        club_a = create_company(name="Club A")
        club_b = create_company(name="Club B")
        _create(db_session, club_a, create_selection(company_id=club_a.id))
        other = _create(db_session, club_b, create_selection(company_id=club_b.id))
        assert other.id is not None

    def test_update_into_an_existing_key_is_rejected(
        self, db_session, create_company, create_selection
    ):
        """Uniqueness is checked on update too — leaving it to the DB constraint
        would surface a raw IntegrityError instead of a 409."""
        company = create_company()
        u15 = create_selection(company_id=company.id, name="U15")
        u17 = create_selection(company_id=company.id, name="U17")
        _create(db_session, company, u15)
        second = _create(db_session, company, u17)

        with pytest.raises(ConflictException, match="already has a membership"):
            MembershipService(db_session).update(
                second.id, MembershipUpdate(selection_id=u15.id)
            )

    def test_updating_a_row_to_its_own_values_is_allowed(
        self, db_session, create_company, create_selection
    ):
        company = create_company()
        row = _create(db_session, company, create_selection(company_id=company.id))
        updated = MembershipService(db_session).update(
            row.id, MembershipUpdate(name="Senior", price=Decimal("6000.00"))
        )
        assert updated.price == Decimal("6000.00")

    def test_selection_from_another_company_is_rejected(
        self, db_session, create_company, create_selection
    ):
        club_a = create_company(name="Club A")
        club_b = create_company(name="Club B")
        with pytest.raises(ValidationException, match="different company"):
            _create(db_session, club_a, create_selection(company_id=club_b.id))

    def test_admin_cannot_edit_another_companys_membership(
        self, db_session, create_company, create_user, create_selection
    ):
        club_a = create_company(name="Club A")
        club_b = create_company(name="Club B")
        row = _create(db_session, club_a, create_selection(company_id=club_a.id))
        outsider = create_user(company_id=club_b.id)

        with pytest.raises(ForbiddenException, match="your own company"):
            MembershipService(db_session).update(
                row.id, MembershipUpdate(price=Decimal("1.00")),
                current_user=outsider,
            )

    def test_delete_removes_the_row(self, db_session, create_company, create_selection):
        company = create_company()
        row = _create(db_session, company, create_selection(company_id=company.id))
        MembershipService(db_session).delete(row.id)
        assert MembershipRepository(db_session).get_by_id(row.id) is None


class TestMembershipEndpoints:

    def test_create_and_list_endpoint(
        self, client, db_session, auth_headers, create_selection
    ):
        headers, user, company = auth_headers
        selection = create_selection(company_id=company.id)
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            resp = client.post("/api/membership/", json={
                "company_id": company.id,
                "selection_id": selection.id,
                "name": "Senior Waterpolo",
                "program": "waterpolo",
                "billing_type": "monthly",
                "price": "5000.00",
            }, headers=headers)
            # create returns just the new id: data is [id]
            assert resp.status_code == 201, resp.text
            item_id = list(resp.json()["data"])[0]

            listed = client.get("/api/membership/", headers=headers)
            assert listed.status_code == 200
            items = listed.json()["data"]["items"]
            assert Decimal(str(items[0]["price"])) == Decimal("5000.00")
            assert items[0]["billing_type"] == "monthly"
            # The list nests the selection too, so a catalog row can be
            # labelled with the squad it prices without a second call.
            assert items[0]["selection"]["id"] == selection.id
            assert items[0]["selection"]["name"] == "U15"

            one = client.get(f"/api/membership/{item_id}", headers=headers)
            assert one.status_code == 200
            assert one.json()["data"]["selection"]["id"] == selection.id

    def test_term_without_months_returns_422(
        self, client, db_session, auth_headers, create_selection
    ):
        headers, user, company = auth_headers
        selection = create_selection(company_id=company.id)
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            resp = client.post("/api/membership/", json={
                "company_id": company.id,
                "selection_id": selection.id,
                "name": "Bad Term",
                "program": "waterpolo",
                "billing_type": "term",
                "price": "15000.00",
            }, headers=headers)
            assert resp.status_code == 422, resp.text

    def test_duplicate_returns_409(
        self, client, db_session, auth_headers, create_selection
    ):
        headers, user, company = auth_headers
        selection = create_selection(company_id=company.id)
        body = {
            "company_id": company.id,
            "selection_id": selection.id,
            "name": "Dup",
            "program": "waterpolo",
            "billing_type": "monthly",
            "price": "5000.00",
        }
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            assert client.post("/api/membership/", json=body, headers=headers).status_code == 201
            second = client.post("/api/membership/", json=body, headers=headers)
            assert second.status_code == 409, second.text

    def test_delete_endpoint(self, client, db_session, auth_headers, create_selection):
        headers, user, company = auth_headers
        selection = create_selection(company_id=company.id)
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            created = client.post("/api/membership/", json={
                "company_id": company.id,
                "selection_id": selection.id,
                "name": "Doomed",
                "program": "swimming",
                "billing_type": "monthly",
                "price": "1000.00",
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
    def other_membership(self, db_session, create_company, create_selection):
        other = create_company(name="Other Club")
        return _create(
            db_session, other, create_selection(company_id=other.id), name="Other Plan"
        )

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

    def test_create_membership_in_other_company_403(
        self, client, create_company, auth_headers, create_selection
    ):
        headers, _, _ = auth_headers
        other = create_company(name="Other Club")
        response = _call(client, "post", "/api/membership/", headers, json={
            "company_id": other.id,
            "selection_id": create_selection(company_id=other.id).id,
            "name": "Sneaky",
            "program": "waterpolo",
            "billing_type": "monthly",
            "price": "1000.00",
        })
        assert response.status_code == 403

    def test_super_admin_sees_other_company_membership(
        self, client, other_membership, super_admin_headers
    ):
        headers, _ = super_admin_headers
        response = _call(client, "get", f"/api/membership/{other_membership.id}", headers)
        assert response.status_code == 200
