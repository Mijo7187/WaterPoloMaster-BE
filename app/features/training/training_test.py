# ============================================
# TRAINING TESTS
# ============================================

import pytest
from decimal import Decimal
from datetime import date, time

from app.features.training.training_service import TrainingService
from app.features.training.training_repository import TrainingRepository
from app.features.training.training_schemas import TrainingCreate, TrainingUpdate, TrainingFilters
from app.features.training.training_model import Training, TrainingStatus
from app.utils.dateUtils import QuarterType
from app.core.api.exceptions import BadRequestException, NotFoundException


# ============================================
# TRAINING REPOSITORY TESTS
# ============================================

class TestTrainingRepository:

    def test_create_training(self, db_session, create_company, create_season):
        company = create_company()
        season = create_season(company_id=company.id)
        repo = TrainingRepository(db_session)
        training = repo.create(
            {
                "company_id": company.id,
                "pool_id": company.id,
                "season_id": season.id,
                "training_date": date(2026, 5, 1),
                "start_time": time(10, 0),
                "end_time": time(11, 0),
                "price": 200,
                "status": TrainingStatus.INCOMING.value,
            }
        )
        assert training.id is not None
        assert training.price == 200

    def test_get_by_id(self, db_session, create_company, create_training):
        company = create_company()
        training = create_training(company_id=company.id)
        repo = TrainingRepository(db_session)
        found = repo.get_by_id(training.id)
        assert found is not None
        assert found.id == training.id

    def test_get_by_id_not_found(self, db_session):
        repo = TrainingRepository(db_session)
        assert repo.get_by_id(9999) is None

    def test_get_list(self, db_session, create_company, create_training):
        company = create_company()
        create_training(company_id=company.id)
        create_training(company_id=company.id)
        repo = TrainingRepository(db_session)
        items, total = repo.get_list(filters=TrainingFilters())
        assert total >= 2

    def test_get_list_filter_by_user_id(self, db_session, create_company, create_training, create_user):
        company = create_company()
        member_training = create_training(company_id=company.id)
        create_training(company_id=company.id)  # no members
        user = create_user(company_id=company.id)

        from app.features.training_users.training_users_model import TrainingUsers
        db_session.add(TrainingUsers(training_id=member_training.id, user_id=user.id))
        db_session.commit()

        repo = TrainingRepository(db_session)

        items, total = repo.get_list(filters=TrainingFilters(user_id=user.id))
        assert total == 1
        assert items[0].id == member_training.id

        # ANDs with other filters — a non-matching company narrows to zero.
        _, none = repo.get_list(filters=TrainingFilters(user_id=user.id, company_id=999999))
        assert none == 0

    def test_update_training(self, db_session, create_company, create_training):
        company = create_company()
        training = create_training(company_id=company.id)
        repo = TrainingRepository(db_session)
        updated = repo.update(training.id, {"price": 500})
        assert updated.price == 500

    def test_update_training_not_found(self, db_session):
        repo = TrainingRepository(db_session)
        assert repo.update(9999, {"price": 500}) is None


# ============================================
# TRAINING SERVICE TESTS
# ============================================

class TestTrainingServiceCreate:

    def test_create_training(self, db_session, create_company, create_season):
        company = create_company()
        season = create_season(company_id=company.id)
        service = TrainingService(db_session)
        training = service.create(TrainingCreate(
            company_id=company.id,
            pool_id=company.id,
            training_date=date(2026, 5, 1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            price=300,
        ))
        assert training.id is not None
        # season is resolved server-side from training_date; quarter_type is derived
        assert training.season_id == season.id
        assert training.quarter_type == QuarterType.Q2

    def test_create_training_without_season_raises(self, db_session, create_company):
        company = create_company()
        service = TrainingService(db_session)
        with pytest.raises(BadRequestException, match="You have to add a Season covering this date"):
            service.create(TrainingCreate(
                company_id=company.id,
                pool_id=company.id,
                training_date=date(2026, 5, 1),
                start_time=time(10, 0),
                end_time=time(11, 0),
                price=300,
            ))


# ============================================
# GROUP LINK — the squad a training belongs to
# ============================================
# group_id is optional, and when it is set it — not the date — decides the
# season. The two columns can therefore never disagree.

class TestTrainingGroupLink:

    def test_group_decides_the_season(
        self, db_session, create_company, create_season, create_selection, create_group
    ):
        company = create_company()
        season = create_season(company_id=company.id)
        selection = create_selection(company_id=company.id)
        group = create_group(season_id=season.id, selection_id=selection.id)

        service = TrainingService(db_session)
        training = service.create(TrainingCreate(
            company_id=company.id,
            pool_id=company.id,
            training_date=date(2026, 5, 1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            price=300,
            group_id=group.id,
        ))

        assert training.group_id == group.id
        assert training.season_id == group.season_id

    def test_group_of_the_academy_works_for_a_member_club(
        self, db_session, create_company, create_season, create_selection, create_group
    ):
        """The club has no season of its own — the academy owns it.

        This is the case the plain date lookup cannot serve: resolve_season_id
        matches Season.company_id against the club and would raise. Going
        through the group resolves it against the academy instead.
        """
        academy = create_company(name="Academy", company_type="ACADEMY")
        club = create_company(name="Member Club", academy_id=academy.id)
        season = create_season(company_id=academy.id)
        selection = create_selection(company_id=club.id)
        group = create_group(season_id=season.id, selection_id=selection.id)

        service = TrainingService(db_session)
        training = service.create(TrainingCreate(
            company_id=club.id,
            pool_id=club.id,
            training_date=date(2026, 5, 1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            price=300,
            group_id=group.id,
        ))

        assert training.season_id == season.id

    def test_date_outside_the_groups_season_raises(
        self, db_session, create_company, create_season, create_selection, create_group
    ):
        company = create_company()
        season = create_season(company_id=company.id)  # 2026-01-01 .. 2026-12-31
        selection = create_selection(company_id=company.id)
        group = create_group(season_id=season.id, selection_id=selection.id)

        service = TrainingService(db_session)
        with pytest.raises(BadRequestException, match="outside the group's season"):
            service.create(TrainingCreate(
                company_id=company.id,
                pool_id=company.id,
                training_date=date(2027, 5, 1),
                start_time=time(10, 0),
                end_time=time(11, 0),
                price=300,
                group_id=group.id,
            ))

    def test_group_from_another_academy_raises(
        self, db_session, create_company, create_season, create_selection, create_group
    ):
        company = create_company()
        other = create_company(name="Other Club")
        season = create_season(company_id=other.id)
        selection = create_selection(company_id=other.id)
        group = create_group(season_id=season.id, selection_id=selection.id)

        service = TrainingService(db_session)
        with pytest.raises(BadRequestException, match="same academy"):
            service.create(TrainingCreate(
                company_id=company.id,
                pool_id=company.id,
                training_date=date(2026, 5, 1),
                start_time=time(10, 0),
                end_time=time(11, 0),
                price=300,
                group_id=group.id,
            ))

    def test_unknown_group_raises(self, db_session, create_company, create_season):
        company = create_company()
        create_season(company_id=company.id)
        service = TrainingService(db_session)
        with pytest.raises(NotFoundException, match="Group not found"):
            service.create(TrainingCreate(
                company_id=company.id,
                pool_id=company.id,
                training_date=date(2026, 5, 1),
                start_time=time(10, 0),
                end_time=time(11, 0),
                price=300,
                group_id=999999,
            ))

    def test_moving_the_group_re_derives_the_season(
        self, db_session, create_company, create_season, create_selection, create_group,
        create_training,
    ):
        company = create_company()
        old_season = create_season(company_id=company.id)
        new_season = create_season(
            company_id=company.id,
            name="2027 Season",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_current=False,
        )
        selection = create_selection(company_id=company.id)
        old_group = create_group(season_id=old_season.id, selection_id=selection.id)
        new_group = create_group(season_id=new_season.id, selection_id=selection.id)

        training = create_training(
            company_id=company.id, training_date=date(2026, 5, 1), group_id=old_group.id
        )
        assert training.season_id == old_season.id

        service = TrainingService(db_session)
        updated = service.update(training.id, TrainingUpdate(
            group_id=new_group.id, training_date=date(2027, 5, 1)
        ))

        assert updated.group_id == new_group.id
        assert updated.season_id == new_season.id

    def test_detaching_the_group_falls_back_to_the_date(
        self, db_session, create_company, create_season, create_selection, create_group,
        create_training,
    ):
        company = create_company()
        season = create_season(company_id=company.id)
        selection = create_selection(company_id=company.id)
        group = create_group(season_id=season.id, selection_id=selection.id)

        training = create_training(
            company_id=company.id, training_date=date(2026, 5, 1), group_id=group.id
        )

        service = TrainingService(db_session)
        updated = service.update(training.id, TrainingUpdate(group_id=None))

        assert updated.group_id is None
        # Still in a season — resolved from the date, as an open session is.
        assert updated.season_id == season.id

    def test_editing_an_unrelated_field_leaves_the_season_alone(
        self, db_session, create_company, create_season, create_selection, create_group,
        create_training,
    ):
        company = create_company()
        season = create_season(company_id=company.id)
        selection = create_selection(company_id=company.id)
        group = create_group(season_id=season.id, selection_id=selection.id)
        training = create_training(company_id=company.id, group_id=group.id)

        service = TrainingService(db_session)
        updated = service.update(training.id, TrainingUpdate(price=777))

        assert updated.price == 777
        assert updated.season_id == season.id
        assert updated.group_id == group.id

    def test_filter_by_group_id(
        self, db_session, create_company, create_season, create_selection, create_group,
        create_training,
    ):
        company = create_company()
        season = create_season(company_id=company.id)
        u15 = create_selection(company_id=company.id, name="U15")
        u17 = create_selection(company_id=company.id, name="U17")
        u15_group = create_group(season_id=season.id, selection_id=u15.id)
        u17_group = create_group(season_id=season.id, selection_id=u17.id)

        mine = create_training(company_id=company.id, group_id=u15_group.id)
        create_training(company_id=company.id, group_id=u17_group.id)
        open_session = create_training(company_id=company.id)  # no group

        repo = TrainingRepository(db_session)

        items, total = repo.get_list(filters=TrainingFilters(group_id=u15_group.id))
        assert total == 1
        assert items[0].id == mine.id
        # The squad's selection rides along on the list response.
        assert items[0].group.selection.name == "U15"

        items, total = repo.get_list(filters=TrainingFilters(group_id__isnull=True))
        assert [i.id for i in items] == [open_session.id]


class TestTrainingServiceGet:

    def test_get_by_id(self, db_session, create_company, create_training):
        company = create_company()
        training = create_training(company_id=company.id)
        service = TrainingService(db_session)
        found = service.get_by_id(training.id)
        assert found.id == training.id

    def test_get_by_id_not_found(self, db_session):
        service = TrainingService(db_session)
        with pytest.raises(NotFoundException):
            service.get_by_id(9999)

    def test_get_list(self, db_session, create_company, create_training):
        company = create_company()
        create_training(company_id=company.id)
        service = TrainingService(db_session)
        items, total = service.get_list(filters=TrainingFilters())
        assert total >= 1


class TestTrainingServiceUpdate:

    def test_update_training(self, db_session, create_company, create_training):
        company = create_company()
        training = create_training(company_id=company.id)
        service = TrainingService(db_session)
        updated = service.update(training.id, TrainingUpdate(price=999))
        assert updated.price == 999

    def test_update_training_status(self, db_session, create_company, create_training):
        company = create_company()
        training = create_training(company_id=company.id)
        service = TrainingService(db_session)
        updated = service.update(training.id, TrainingUpdate(status=TrainingStatus.FINISHED))
        assert updated.status == TrainingStatus.FINISHED.value

    def test_update_training_not_found(self, db_session):
        service = TrainingService(db_session)
        with pytest.raises(NotFoundException):
            service.update(9999, TrainingUpdate(price=100))


# ============================================
# TRAINING ROUTER / ENDPOINT TESTS
# ============================================

class TestTrainingEndpoints:

    def test_create_training_endpoint(self, client, db_session, create_company, create_season, auth_headers):
        headers, user, company = auth_headers
        create_season(company_id=company.id)
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.post("/api/training/", json={
                "company_id": company.id,
                "pool_id": company.id,
                "training_date": "2026-05-01",
                "start_time": "10:00:00",
                "end_time": "11:00:00",
                "price": 100,
            }, headers=headers)
            assert response.status_code == 201

    def test_get_trainings_endpoint(self, client, db_session, create_company, create_training, auth_headers):
        headers, user, company = auth_headers
        create_training(company_id=company.id)
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.get("/api/training/", headers=headers)
            assert response.status_code == 200
            assert isinstance(response.json()["data"]["items"], list)

    def test_get_training_by_id_endpoint(self, client, db_session, create_company, create_training, auth_headers):
        headers, user, company = auth_headers
        training = create_training(company_id=company.id)
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.get(f"/api/training/{training.id}", headers=headers)
            assert response.status_code == 200
            # training_date defaults to 2026-04-01 (April -> Q2)
            assert response.json()["data"]["quarter_type"] == "Q2"

    def test_update_training_endpoint(self, client, db_session, create_company, create_training, auth_headers):
        headers, user, company = auth_headers
        training = create_training(company_id=company.id)
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.put(f"/api/training/{training.id}", json={
                "price": 999,
            }, headers=headers)
            assert response.status_code == 200

    def test_create_training_unauthenticated(self, client):
        response = client.post("/api/training/", json={
            "company_id": 1,
            "training_date": "2026-05-01",
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "price": 100,
        })
        assert response.status_code in (401, 403)


def _call(client, method, url, headers, **kwargs):
    from unittest.mock import patch
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


class TestTrainingCompanyScope:
    """Non-SUPER_ADMIN users only see and manage trainings of their own company."""

    def test_list_only_own_company(self, client, create_company, create_training, auth_headers):
        headers, _, company = auth_headers
        mine = create_training(company_id=company.id)
        other = create_training(company_id=create_company(name="Other Club").id)

        response = _call(client, "get", "/api/training/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert mine.id in ids
        assert other.id not in ids

    def test_list_company_filter_cannot_widen_scope(self, client, create_company, create_training, auth_headers):
        headers, _, _ = auth_headers
        other_company = create_company(name="Other Club")
        create_training(company_id=other_company.id)

        response = _call(client, "get", f"/api/training/?company_id={other_company.id}", headers)
        assert response.status_code == 200
        assert response.json()["data"]["items"] == []

    def test_get_other_company_training_403(self, client, create_company, create_training, auth_headers):
        headers, _, _ = auth_headers
        other = create_training(company_id=create_company(name="Other Club").id)

        response = _call(client, "get", f"/api/training/{other.id}", headers)
        assert response.status_code == 403

    def test_update_other_company_training_403(self, client, create_company, create_training, auth_headers):
        headers, _, _ = auth_headers
        other = create_training(company_id=create_company(name="Other Club").id)

        response = _call(client, "put", f"/api/training/{other.id}", headers, json={"price": 1})
        assert response.status_code == 403

    def test_move_training_to_other_company_403(self, client, create_company, create_training, auth_headers):
        headers, _, company = auth_headers
        training = create_training(company_id=company.id)
        other_company = create_company(name="Other Club")

        response = _call(client, "put", f"/api/training/{training.id}", headers,
                         json={"company_id": other_company.id})
        assert response.status_code == 403

    def test_create_training_in_other_company_403(self, client, create_company, create_season, auth_headers):
        headers, _, _ = auth_headers
        other_company = create_company(name="Other Club")
        create_season(company_id=other_company.id)

        response = _call(client, "post", "/api/training/", headers, json={
            "company_id": other_company.id,
            "pool_id": other_company.id,
            "training_date": "2026-05-01",
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "price": 100,
        })
        assert response.status_code == 403

    def test_super_admin_sees_other_company_training(self, client, create_company, create_training, super_admin_headers):
        headers, _ = super_admin_headers
        other = create_training(company_id=create_company(name="Other Club").id)

        response = _call(client, "get", f"/api/training/{other.id}", headers)
        assert response.status_code == 200


# ============================================
# List summary
# ============================================

class TestTrainingSummary:

    def test_counts_and_total_price(self, db_session, create_company, create_training):
        company = create_company()
        create_training(company_id=company.id, price=100)
        create_training(company_id=company.id, price=50, status=TrainingStatus.FINISHED.value)
        create_training(company_id=company.id, price=999, status=TrainingStatus.CANCELLED.value)

        summary = TrainingService(db_session).get_summary(TrainingFilters(company_id=company.id))
        assert summary["count"] == 3
        assert summary["by_status"] == {
            "FINISHED": 1, "IN_PROCESS": 0, "CANCELLED": 1, "INCOMING": 1,
        }
        assert summary["total_price"] == Decimal("150")

    def test_list_endpoint_carries_scoped_summary(self, client, create_company, create_training, auth_headers):
        headers, _, company = auth_headers
        create_training(company_id=company.id, price=100)
        create_training(company_id=create_company(name="Other Club").id, price=500)

        data = _call(client, "get", "/api/training/", headers).json()["data"]
        assert data["summary"]["count"] == 1
        assert Decimal(str(data["summary"]["total_price"])) == Decimal("100")

    def test_list_without_summary_returns_null(self, client, super_admin_headers):
        headers, _ = super_admin_headers
        data = _call(client, "get", "/api/company/", headers).json()["data"]
        assert data["summary"] is None
