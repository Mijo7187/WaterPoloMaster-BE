# ============================================
# GROUP TESTS — a selection in a season
# ============================================

from unittest.mock import patch

import pytest

from app.features.group.group_model import Group
from app.features.users.users_models import UserRole

URL = "/api/group/"


def _call(client, method, url, headers, **kwargs):
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


@pytest.fixture()
def own(auth_headers, create_season, create_selection, create_user):
    """Season, two selections and a player, all in the admin's company."""
    headers, _, company = auth_headers
    return {
        "headers": headers,
        "company": company,
        "season": create_season(company_id=company.id),
        "u15": create_selection(company_id=company.id, name="U15"),
        "u17": create_selection(company_id=company.id, name="U17"),
        "player": create_user(
            email="player@test.com", username="player", company_id=company.id
        ),
    }


@pytest.fixture()
def other(create_company, create_season, create_selection, create_user):
    """The same set, in a second, unrelated company."""
    company = create_company(name="Other Club")
    return {
        "company": company,
        "season": create_season(company_id=company.id, name="Other Season"),
        "selection": create_selection(company_id=company.id, name="U15"),
        "player": create_user(
            email="other@test.com", username="other", company_id=company.id
        ),
    }


@pytest.fixture()
def coach_headers(own, create_user, mock_redis):
    from app.core.security import create_access_token

    user = create_user(
        email="coach@test.com",
        username="coach",
        roles=[UserRole.COACH],
        company_id=own["company"].id,
    )
    token = create_access_token({
        "sub": user.email, "user_id": user.id, "roles": user.roles, "type": "access",
    })
    mock_redis["store_access_token"](user.id, token)
    return {"Authorization": f"Bearer {token}"}


def _body(season, selection):
    return {"season_id": season.id, "selection_id": selection.id}


class TestCreate:
    def test_happy_path_returns_nested(self, client, own):
        response = _call(
            client, "post", URL, own["headers"], json=_body(own["season"], own["u15"])
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["season"]["id"] == own["season"].id
        assert data["selection"]["name"] == "U15"

    def test_two_selections_same_season(self, client, own):
        for selection in (own["u15"], own["u17"]):
            response = _call(
                client, "post", URL, own["headers"], json=_body(own["season"], selection)
            )
            assert response.status_code == 201

    def test_exact_duplicate_409(self, client, own):
        body = _body(own["season"], own["u15"])
        assert _call(client, "post", URL, own["headers"], json=body).status_code == 201
        assert _call(client, "post", URL, own["headers"], json=body).status_code == 409

    def test_unrelated_companies_400(self, client, own, other):
        response = _call(
            client, "post", URL, own["headers"],
            json=_body(own["season"], other["selection"]),
        )
        assert response.status_code == 400

    def test_same_academy_is_allowed(
        self, client, db_session, own, create_company, create_season, super_admin_headers
    ):
        """Seasons live on the ACADEMY while selections belong to its clubs, so
        "same company" would be too strict a test."""
        headers, _ = super_admin_headers
        academy = create_company(name="Academy")
        own["company"].academy_id = academy.id
        db_session.commit()
        academy_season = create_season(company_id=academy.id, name="Academy Season")

        response = _call(
            client, "post", URL, headers, json=_body(academy_season, own["u15"])
        )
        assert response.status_code == 201, response.text

    def test_inactive_selection_400(self, client, own, create_selection):
        retired = create_selection(
            company_id=own["company"].id, name="Old", is_active=False
        )
        response = _call(
            client, "post", URL, own["headers"], json=_body(own["season"], retired)
        )
        assert response.status_code == 400

    def test_missing_season_404(self, client, own):
        body = _body(own["season"], own["u15"]) | {"season_id": 99999}
        assert _call(client, "post", URL, own["headers"], json=body).status_code == 404

    def test_admin_other_company_403(self, client, own, other):
        response = _call(
            client, "post", URL, own["headers"],
            json=_body(other["season"], other["selection"]),
        )
        assert response.status_code == 403

    def test_super_admin_other_company_201(self, client, other, super_admin_headers):
        headers, _ = super_admin_headers
        response = _call(
            client, "post", URL, headers,
            json=_body(other["season"], other["selection"]),
        )
        assert response.status_code == 201


class TestGetOrCreate:
    """The entry point the MEMBERSHIP contract hook uses."""

    def test_creates_once_then_returns_the_same_row(self, db_session, own):
        from app.features.group.group_service import GroupService

        service = GroupService(db_session)
        first = service.get_or_create(own["season"].id, own["u15"].id)
        second = service.get_or_create(own["season"].id, own["u15"].id)

        assert first.id == second.id
        assert db_session.query(Group).count() == 1


class TestListAndGet:
    def test_list_scoped_to_own_company(self, client, own, other, create_group):
        mine = create_group(own["season"].id, own["u15"].id)
        theirs = create_group(other["season"].id, other["selection"].id)

        response = _call(client, "get", URL, own["headers"])
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert mine.id in ids
        assert theirs.id not in ids

    def test_super_admin_sees_all(
        self, client, own, other, create_group, super_admin_headers
    ):
        mine = create_group(own["season"].id, own["u15"].id)
        theirs = create_group(other["season"].id, other["selection"].id)
        headers, _ = super_admin_headers

        ids = {i["id"] for i in _call(client, "get", URL, headers).json()["data"]["items"]}
        assert {mine.id, theirs.id} <= ids

    def test_filter_by_season(self, client, own, create_group):
        a = create_group(own["season"].id, own["u15"].id)
        b = create_group(own["season"].id, own["u17"].id)

        response = _call(
            client, "get", f"{URL}?season_id={own['season'].id}", own["headers"]
        )
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert ids == {a.id, b.id}

    def test_filter_by_selection(self, client, own, create_group):
        a = create_group(own["season"].id, own["u15"].id)
        create_group(own["season"].id, own["u17"].id)

        response = _call(
            client, "get", f"{URL}?selection_id={own['u15'].id}", own["headers"]
        )
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert ids == {a.id}

    def test_get_other_company_403(self, client, own, other, create_group):
        theirs = create_group(other["season"].id, other["selection"].id)
        response = _call(client, "get", f"{URL}{theirs.id}", own["headers"])
        assert response.status_code == 403


class TestDelete:
    def test_delete_own(self, client, own, create_group, db_session):
        group = create_group(own["season"].id, own["u15"].id)
        response = _call(client, "delete", f"{URL}{group.id}", own["headers"])
        assert response.status_code == 200
        db_session.expire_all()
        assert db_session.get(Group, group.id) is None

    def test_delete_other_company_403(self, client, own, other, create_group):
        theirs = create_group(other["season"].id, other["selection"].id)
        response = _call(client, "delete", f"{URL}{theirs.id}", own["headers"])
        assert response.status_code == 403

    def test_delete_missing_404(self, client, own):
        response = _call(client, "delete", f"{URL}99999", own["headers"])
        assert response.status_code == 404


class TestCoachPermissions:
    def test_coach_can_view(self, client, own, coach_headers, create_group):
        group = create_group(own["season"].id, own["u15"].id)
        assert _call(client, "get", URL, coach_headers).status_code == 200
        assert _call(client, "get", f"{URL}{group.id}", coach_headers).status_code == 200

    def test_coach_cannot_create_or_delete(self, client, own, coach_headers, create_group):
        body = _body(own["season"], own["u15"])
        assert _call(client, "post", URL, coach_headers, json=body).status_code == 403

        group = create_group(own["season"].id, own["u15"].id)
        assert _call(client, "delete", f"{URL}{group.id}", coach_headers).status_code == 403
