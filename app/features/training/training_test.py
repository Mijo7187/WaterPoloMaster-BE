# ============================================
# TRAINING TESTS
# ============================================

import pytest
from datetime import date, time

from app.features.training.training_service import TrainingService
from app.features.training.training_repository import TrainingRepository
from app.features.training.training_schemas import TrainingCreate, TrainingUpdate, TrainingFilters
from app.features.training.training_model import Training, TrainingStatus
from app.core.api.exceptions import NotFoundException


# ============================================
# TRAINING REPOSITORY TESTS
# ============================================

class TestTrainingRepository:

    def test_create_training(self, db_session, create_company, create_training_type):
        company = create_company()
        training_type = create_training_type(company_id=company.id)
        repo = TrainingRepository(db_session)
        training = repo.create(
            {
                "company_id": company.id,
                "pool_id": company.id,
                "training_type_id": training_type.id,
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

    def test_create_training(self, db_session, create_company, create_training_type):
        company = create_company()
        training_type = create_training_type(company_id=company.id)
        service = TrainingService(db_session)
        training = service.create(TrainingCreate(
            company_id=company.id,
            pool_id=company.id,
            training_type_id=training_type.id,
            training_date=date(2026, 5, 1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            price=300,
        ))
        assert training.id is not None


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

    def test_create_training_endpoint(self, client, db_session, create_company, create_training_type, auth_headers):
        headers, user, company = auth_headers
        training_type = create_training_type(company_id=company.id)
        from unittest.mock import patch
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            response = client.post("/api/training/", json={
                "company_id": company.id,
                "pool_id": company.id,
                "training_type_id": training_type.id,
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
