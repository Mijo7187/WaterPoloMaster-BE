# ============================================
# GROUP USER TESTS — who is in a group
# ============================================

from unittest.mock import patch

import pytest

from app.features.group.group_model import Group
from app.features.group_user.group_user_model import GroupUser
from app.features.sifarnici.selection.selection_model import Selection
from app.features.users.users_models import UserRole

URL = "/api/group-user/"


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
def create_group(db_session):
    def _create(season_id, selection_id):
        group = Group(season_id=season_id, selection_id=selection_id)
        db_session.add(group)
        db_session.commit()
        db_session.refresh(group)
        return group
    return _create


@pytest.fixture()
def create_member(db_session):
    def _create(group_id, user_id):
        row = GroupUser(group_id=group_id, user_id=user_id)
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        return row
    return _create


@pytest.fixture()
def own(auth_headers, create_season, create_selection, create_group, create_user):
    """Two groups and a player, all in the admin's company."""
    headers, _, company = auth_headers
    season = create_season(company_id=company.id)
    return {
        "headers": headers,
        "company": company,
        "season": season,
        "u15": create_group(season.id, create_selection(company_id=company.id, name="U15").id),
        "u17": create_group(season.id, create_selection(company_id=company.id, name="U17").id),
        "player": create_user(
            email="player@test.com", username="player", company_id=company.id
        ),
    }


@pytest.fixture()
def other(create_company, create_season, create_selection, create_group, create_user):
    """The same set, in a second, unrelated company."""
    company = create_company(name="Other Club")
    season = create_season(company_id=company.id, name="Other Season")
    return {
        "company": company,
        "season": season,
        "group": create_group(season.id, create_selection(company_id=company.id).id),
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


def _body(group, user):
    return {"group_id": group.id, "user_id": user.id}


class TestCreate:
    def test_happy_path_returns_nested(self, client, own):
        response = _call(
            client, "post", URL, own["headers"], json=_body(own["u15"], own["player"])
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["user"]["id"] == own["player"].id
        # The nested group carries its own season and selection.
        assert data["group"]["selection"]["name"] == "U15"
        assert data["group"]["season"]["id"] == own["season"].id

    def test_a_player_can_hold_two_groups_in_one_season(self, client, own):
        for group in (own["u15"], own["u17"]):
            response = _call(
                client, "post", URL, own["headers"], json=_body(group, own["player"])
            )
            assert response.status_code == 201

    def test_exact_duplicate_409(self, client, own):
        body = _body(own["u15"], own["player"])
        assert _call(client, "post", URL, own["headers"], json=body).status_code == 201
        assert _call(client, "post", URL, own["headers"], json=body).status_code == 409

    def test_player_from_an_unrelated_company_400(self, client, own, other):
        response = _call(
            client, "post", URL, own["headers"], json=_body(own["u15"], other["player"])
        )
        assert response.status_code == 400

    def test_missing_group_404(self, client, own):
        body = _body(own["u15"], own["player"]) | {"group_id": 99999}
        assert _call(client, "post", URL, own["headers"], json=body).status_code == 404

    def test_missing_user_404(self, client, own):
        body = _body(own["u15"], own["player"]) | {"user_id": 99999}
        assert _call(client, "post", URL, own["headers"], json=body).status_code == 404

    def test_admin_other_company_403(self, client, own, other):
        response = _call(
            client, "post", URL, own["headers"],
            json=_body(other["group"], other["player"]),
        )
        assert response.status_code == 403

    def test_super_admin_other_company_201(self, client, other, super_admin_headers):
        headers, _ = super_admin_headers
        response = _call(
            client, "post", URL, headers, json=_body(other["group"], other["player"])
        )
        assert response.status_code == 201


class TestEnrolIfAbsent:
    """The idempotent entry point the MEMBERSHIP contract hook uses."""

    def test_second_call_is_a_no_op(self, db_session, own):
        from app.features.group_user.group_user_service import GroupUserService

        service = GroupUserService(db_session)
        created = service.enrol_if_absent(own["u15"].id, own["player"].id)
        again = service.enrol_if_absent(own["u15"].id, own["player"].id)

        assert created is not None
        assert again is None
        assert db_session.query(GroupUser).count() == 1


class TestListAndGet:
    def test_list_scoped_to_own_company(self, client, own, other, create_member):
        mine = create_member(own["u15"].id, own["player"].id)
        theirs = create_member(other["group"].id, other["player"].id)

        response = _call(client, "get", URL, own["headers"])
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert mine.id in ids
        assert theirs.id not in ids

    def test_super_admin_sees_all(
        self, client, own, other, create_member, super_admin_headers
    ):
        mine = create_member(own["u15"].id, own["player"].id)
        theirs = create_member(other["group"].id, other["player"].id)
        headers, _ = super_admin_headers

        ids = {i["id"] for i in _call(client, "get", URL, headers).json()["data"]["items"]}
        assert {mine.id, theirs.id} <= ids

    def test_filter_squad_of_group(self, client, own, create_user, create_member):
        teammate = create_user(
            email="mate@test.com", username="mate", company_id=own["company"].id
        )
        a = create_member(own["u15"].id, own["player"].id)
        b = create_member(own["u15"].id, teammate.id)
        create_member(own["u17"].id, own["player"].id)

        response = _call(
            client, "get", f"{URL}?group_id={own['u15'].id}", own["headers"]
        )
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert ids == {a.id, b.id}

    def test_filter_groups_of_player(self, client, own, create_member):
        create_member(own["u15"].id, own["player"].id)
        create_member(own["u17"].id, own["player"].id)

        response = _call(
            client, "get", f"{URL}?user_id={own['player'].id}", own["headers"]
        )
        names = {
            i["group"]["selection"]["name"]
            for i in response.json()["data"]["items"]
        }
        assert names == {"U15", "U17"}

    def test_get_other_company_403(self, client, own, other, create_member):
        theirs = create_member(other["group"].id, other["player"].id)
        response = _call(client, "get", f"{URL}{theirs.id}", own["headers"])
        assert response.status_code == 403


class TestDelete:
    def test_delete_own(self, client, own, create_member, db_session):
        row = create_member(own["u15"].id, own["player"].id)
        response = _call(client, "delete", f"{URL}{row.id}", own["headers"])
        assert response.status_code == 200
        db_session.expire_all()
        assert db_session.get(GroupUser, row.id) is None

    def test_delete_other_company_403(self, client, own, other, create_member):
        theirs = create_member(other["group"].id, other["player"].id)
        response = _call(client, "delete", f"{URL}{theirs.id}", own["headers"])
        assert response.status_code == 403

    def test_delete_missing_404(self, client, own):
        response = _call(client, "delete", f"{URL}99999", own["headers"])
        assert response.status_code == 404

    def test_deleting_the_group_removes_its_members(
        self, client, own, create_member, db_session
    ):
        """The roster cascades with the squad it belongs to."""
        row = create_member(own["u15"].id, own["player"].id)

        _call(client, "delete", f"/api/group/{own['u15'].id}", own["headers"])

        db_session.expire_all()
        assert db_session.get(GroupUser, row.id) is None


class TestCoachPermissions:
    def test_coach_can_view(self, client, own, coach_headers, create_member):
        row = create_member(own["u15"].id, own["player"].id)
        assert _call(client, "get", URL, coach_headers).status_code == 200
        assert _call(client, "get", f"{URL}{row.id}", coach_headers).status_code == 200

    def test_coach_cannot_create_or_delete(self, client, own, coach_headers, create_member):
        body = _body(own["u15"], own["player"])
        assert _call(client, "post", URL, coach_headers, json=body).status_code == 403

        row = create_member(own["u15"].id, own["player"].id)
        assert _call(client, "delete", f"{URL}{row.id}", coach_headers).status_code == 403
