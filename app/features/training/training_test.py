import pytest
from datetime import datetime, timezone

from app.common.crud.crud_schemas import CrudFilters
from app.core.api.exceptions import NotFoundException
from app.features.training.training_model import TrainingStatus
from app.features.training.training_repository import TrainingRepository
from app.features.training.training_schemas import TrainingCreate, TrainingUpdate
from app.features.training.training_service import TrainingService


class TestTrainingRepository:

    def test_create_training(self, db_session, create_company):
        company = create_company()
        repo = TrainingRepository(db_session)
        training = repo.create({
            "company_id": company.id,
            "start_training_date_time": datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            "end_training_date_time": datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
            "price": 200,
            "payed": False,
            "status": TrainingStatus.INCOMING.value,
        })
        assert training.id is not None
        assert training.price == 200

    def test_create_training_with_users(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="player@test.com", company_id=company.id)
        repo = TrainingRepository(db_session)
        training = repo.create({
            "company_id": company.id,
            "start_training_date_time": datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            "end_training_date_time": datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
            "price": 100,
            "payed": False,
            "status": TrainingStatus.INCOMING.value,
            "users_list": [user.id],
        })
        assert len(training.users) == 1
        assert training.users[0].id == user.id

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
        items, _ = repo.get_list(CrudFilters())
        assert len(items) == 2

    def test_get_list_pagination(self, db_session, create_company, create_training):
        company = create_company()
        for _ in range(5):
            create_training(company_id=company.id)
        repo = TrainingRepository(db_session)
        items, _ = repo.get_list(CrudFilters(size=2))
        assert len(items) == 2

    def test_update_training(self, db_session, create_company, create_training):
        company = create_company()
        training = create_training(company_id=company.id)
        repo = TrainingRepository(db_session)
        updated = repo.update(training.id, {"price": 500})
        assert updated.price == 500

    def test_update_training_not_found(self, db_session):
        repo = TrainingRepository(db_session)
        assert repo.update(9999, {"price": 500}) is None

    def test_update_training_users(self, db_session, create_company, create_training, create_user):
        company = create_company()
        user = create_user(email="newplayer@test.com", company_id=company.id)
        training = create_training(company_id=company.id)
        repo = TrainingRepository(db_session)
        updated = repo.update(training.id, {"users_list": [user.id]})
        assert len(updated.users) == 1


class TestTrainingServiceCreate:

    def test_create_training(self, db_session, create_company):
        company = create_company()
        service = TrainingService(db_session)
        training = service.create(TrainingCreate(
            company_id=company.id,
            start_training_date_time=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            end_training_date_time=datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
            price=300,
        ))
        assert training.id is not None

    def test_create_training_with_users(self, db_session, create_company, create_user):
        company = create_company()
        user = create_user(email="svc@test.com", company_id=company.id)
        service = TrainingService(db_session)
        training = service.create(TrainingCreate(
            company_id=company.id,
            start_training_date_time=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            end_training_date_time=datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
            price=100,
            users_list=[user.id],
        ))
        assert len(training.users) == 1


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
        items, _ = service.get_list(CrudFilters())
        assert len(items) >= 1


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

    def test_update_training_users(self, db_session, create_company, create_training, create_user):
        company = create_company()
        user = create_user(email="updplayer@test.com", company_id=company.id)
        training = create_training(company_id=company.id)
        service = TrainingService(db_session)
        updated = service.update(training.id, TrainingUpdate(users_list=[user.id]))
        assert len(updated.users) == 1


class TestTrainingEndpoints:

    def test_create_training_endpoint(self, client, db_session, create_company, auth_headers):
        headers, user, company = auth_headers
        response = client.post("/api/training/", json={
            "company_id": company.id,
            "start_training_date_time": "2026-05-01T10:00:00Z",
            "end_training_date_time": "2026-05-01T11:00:00Z",
            "price": 100,
        }, headers=headers)
        assert response.status_code == 201

    def test_get_trainings_endpoint(self, client, db_session, create_company, create_training, auth_headers):
        headers, user, company = auth_headers
        create_training(company_id=company.id)
        response = client.get("/api/training/", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json()["data"]["items"], list)

    def test_get_training_by_id_endpoint(self, client, db_session, create_company, create_training, auth_headers):
        headers, user, company = auth_headers
        training = create_training(company_id=company.id)
        response = client.get(f"/api/training/{training.id}", headers=headers)
        assert response.status_code == 200

    def test_update_training_endpoint(self, client, db_session, create_company, create_training, auth_headers):
        headers, user, company = auth_headers
        training = create_training(company_id=company.id)
        response = client.put(f"/api/training/{training.id}", json={
            "price": 999,
        }, headers=headers)
        assert response.status_code == 200

    def test_create_training_unauthenticated(self, client):
        response = client.post("/api/training/", json={
            "company_id": 1,
            "start_training_date_time": "2026-05-01T10:00:00Z",
            "end_training_date_time": "2026-05-01T11:00:00Z",
            "price": 100,
        })
        assert response.status_code in (401, 403)
