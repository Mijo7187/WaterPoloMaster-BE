# ============================================
# SEASON SELECTION USER TESTS
# ============================================

from unittest.mock import patch

import pytest

from app.features.season_selection_user.season_selection_user_model import SeasonSelectionUser
from app.features.sifarnici.selection.selection_model import Selection
from app.features.users.users_models import UserRole

URL = "/api/season-selection-users/"


def _call(client, method, url, headers, **kwargs):
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


@pytest.fixture()
def create_selection(db_session):
    def _create(company_id, name="U15", **kwargs):
        selection = Selection(company_id=company_id, name=name, **kwargs)
        db_session.add(selection)
        db_session.commit()
        db_session.refresh(selection)
        return selection
    return _create


@pytest.fixture()
def create_link(db_session):
    def _create(season_id, selection_id, user_id):
        link = SeasonSelectionUser(
            season_id=season_id, selection_id=selection_id, user_id=user_id
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)
        return link
    return _create


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
    """The same set, in a second company."""
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


def _body(season, selection, user):
    return {"season_id": season.id, "selection_id": selection.id, "user_id": user.id}


class TestCreate:
    def test_happy_path_returns_nested(self, client, own):
        response = _call(
            client, "post", URL, own["headers"],
            json=_body(own["season"], own["u15"], own["player"]),
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["season"]["id"] == own["season"].id
        assert data["selection"]["name"] == "U15"
        assert data["user"]["id"] == own["player"].id

    def test_two_selections_same_season(self, client, own):
        for selection in (own["u15"], own["u17"]):
            response = _call(
                client, "post", URL, own["headers"],
                json=_body(own["season"], selection, own["player"]),
            )
            assert response.status_code == 201

    def test_exact_duplicate_409(self, client, own):
        body = _body(own["season"], own["u15"], own["player"])
        assert _call(client, "post", URL, own["headers"], json=body).status_code == 201
        assert _call(client, "post", URL, own["headers"], json=body).status_code == 409

    def test_mixed_companies_400(self, client, own, other):
        response = _call(
            client, "post", URL, own["headers"],
            json=_body(own["season"], other["selection"], own["player"]),
        )
        assert response.status_code == 400

    def test_inactive_selection_400(self, client, own, create_selection):
        retired = create_selection(
            company_id=own["company"].id, name="Old", is_active=False
        )
        response = _call(
            client, "post", URL, own["headers"],
            json=_body(own["season"], retired, own["player"]),
        )
        assert response.status_code == 400

    def test_missing_season_404(self, client, own):
        body = _body(own["season"], own["u15"], own["player"]) | {"season_id": 99999}
        assert _call(client, "post", URL, own["headers"], json=body).status_code == 404

    def test_admin_other_company_403(self, client, own, other):
        response = _call(
            client, "post", URL, own["headers"],
            json=_body(other["season"], other["selection"], other["player"]),
        )
        assert response.status_code == 403

    def test_super_admin_other_company_201(self, client, other, super_admin_headers):
        headers, _ = super_admin_headers
        response = _call(
            client, "post", URL, headers,
            json=_body(other["season"], other["selection"], other["player"]),
        )
        assert response.status_code == 201


class TestListAndGet:
    def test_list_scoped_to_own_company(self, client, own, other, create_link):
        mine = create_link(own["season"].id, own["u15"].id, own["player"].id)
        theirs = create_link(other["season"].id, other["selection"].id, other["player"].id)

        response = _call(client, "get", URL, own["headers"])
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert mine.id in ids
        assert theirs.id not in ids

    def test_super_admin_sees_all(self, client, own, other, create_link, super_admin_headers):
        mine = create_link(own["season"].id, own["u15"].id, own["player"].id)
        theirs = create_link(other["season"].id, other["selection"].id, other["player"].id)
        headers, _ = super_admin_headers

        ids = {i["id"] for i in _call(client, "get", URL, headers).json()["data"]["items"]}
        assert {mine.id, theirs.id} <= ids

    def test_filter_squad_of_selection(self, client, own, create_user, create_link):
        teammate = create_user(
            email="mate@test.com", username="mate", company_id=own["company"].id
        )
        a = create_link(own["season"].id, own["u15"].id, own["player"].id)
        b = create_link(own["season"].id, own["u15"].id, teammate.id)
        create_link(own["season"].id, own["u17"].id, own["player"].id)

        response = _call(
            client, "get",
            f"{URL}?season_id={own['season'].id}&selection_id={own['u15'].id}",
            own["headers"],
        )
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert ids == {a.id, b.id}

    def test_filter_selections_of_player(self, client, own, create_link):
        create_link(own["season"].id, own["u15"].id, own["player"].id)
        create_link(own["season"].id, own["u17"].id, own["player"].id)

        response = _call(
            client, "get",
            f"{URL}?season_id={own['season'].id}&user_id={own['player'].id}",
            own["headers"],
        )
        names = {i["selection"]["name"] for i in response.json()["data"]["items"]}
        assert names == {"U15", "U17"}

    def test_get_other_company_403(self, client, own, other, create_link):
        theirs = create_link(other["season"].id, other["selection"].id, other["player"].id)
        response = _call(client, "get", f"{URL}{theirs.id}", own["headers"])
        assert response.status_code == 403


class TestDelete:
    def test_delete_own(self, client, own, create_link, db_session):
        link = create_link(own["season"].id, own["u15"].id, own["player"].id)
        response = _call(client, "delete", f"{URL}{link.id}", own["headers"])
        assert response.status_code == 200
        db_session.expire_all()
        assert db_session.get(SeasonSelectionUser, link.id) is None

    def test_delete_other_company_403(self, client, own, other, create_link):
        theirs = create_link(other["season"].id, other["selection"].id, other["player"].id)
        response = _call(client, "delete", f"{URL}{theirs.id}", own["headers"])
        assert response.status_code == 403

    def test_delete_missing_404(self, client, own):
        response = _call(client, "delete", f"{URL}99999", own["headers"])
        assert response.status_code == 404


class TestCoachPermissions:
    def test_coach_can_view(self, client, own, coach_headers, create_link):
        link = create_link(own["season"].id, own["u15"].id, own["player"].id)
        assert _call(client, "get", URL, coach_headers).status_code == 200
        assert _call(client, "get", f"{URL}{link.id}", coach_headers).status_code == 200

    def test_coach_cannot_create_or_delete(self, client, own, coach_headers, create_link):
        body = _body(own["season"], own["u15"], own["player"])
        assert _call(client, "post", URL, coach_headers, json=body).status_code == 403

        link = create_link(own["season"].id, own["u15"].id, own["player"].id)
        assert _call(client, "delete", f"{URL}{link.id}", coach_headers).status_code == 403
