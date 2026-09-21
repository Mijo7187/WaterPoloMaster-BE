# ============================================
# EXERCISE OPTION (sifarnik) TESTS
# ============================================

import pytest
from unittest.mock import patch

from app.features.sifarnici.exercise_option.exercise_option_repository import ExerciseOptionRepository
from app.features.sifarnici.exercise_option.exercise_option_schemas import ExerciseOptionFilters
from app.features.training_segments.training_segments_model import SegmentType


class TestExerciseOptionRepository:

    def test_create_and_get(self, db_session, create_company):
        company = create_company()
        repo = ExerciseOptionRepository(db_session)
        option = repo.create({
            "company_id": company.id,
            "segment_type": SegmentType.SWIMMING,
            "code": "freestyle",
            "name": "Freestyle",
            "is_active": True,
        })
        assert option.id is not None
        assert repo.get_by_id(option.id).code == "freestyle"

    def test_filter_by_segment_type(self, db_session, create_company, create_exercise_option):
        company = create_company()
        create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code="free", name="Free")
        create_exercise_option(segment_type=SegmentType.GYM, company_id=company.id, code="bench", name="Bench")
        repo = ExerciseOptionRepository(db_session)

        items, total = repo.get_list(filters=ExerciseOptionFilters(segment_type=SegmentType.GYM))
        assert total == 1
        assert items[0].code == "bench"

    def test_filter_by_company(self, db_session, create_company, create_exercise_option):
        club_a = create_company(name="Club A")
        club_b = create_company(name="Club B")
        create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=club_a.id, code="free", name="Free")
        create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=club_b.id, code="free", name="Free")
        repo = ExerciseOptionRepository(db_session)

        items, total = repo.get_list(filters=ExerciseOptionFilters(company_id=club_b.id))
        assert total == 1
        assert items[0].company_id == club_b.id

    def test_unique_per_company_segment_type_code(self, db_session, create_company, create_exercise_option):
        company = create_company()
        create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code="free", name="Free")
        with pytest.raises(Exception):
            create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code="free", name="Dup")

    def test_same_code_allowed_in_another_company(self, db_session, create_company, create_exercise_option):
        club_a = create_company(name="Club A")
        club_b = create_company(name="Club B")
        create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=club_a.id, code="free", name="Free")
        other = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=club_b.id, code="free", name="Free")
        assert other.id is not None


class TestExerciseOptionEndpoints:

    def test_create_and_list_endpoint(self, client, db_session, auth_headers):
        headers, user, company = auth_headers
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            resp = client.post("/api/exercise-option/", json={
                "company_id": company.id,
                "segment_type": "WORK_WITH_BALL",
                "code": "passing",
                "name": "Passing drill",
            }, headers=headers)
            assert resp.status_code == 201, resp.text

            listed = client.get("/api/exercise-option/", headers=headers)
            assert listed.status_code == 200
            assert isinstance(listed.json()["data"]["items"], list)


def _call(client, method, url, headers, **kwargs):
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


class TestExerciseOptionCompanyScope:
    """Exercise options are per company — a non-SUPER_ADMIN only sees their own."""

    @pytest.fixture()
    def other_option(self, create_company, create_exercise_option):
        return create_exercise_option(
            segment_type=SegmentType.SWIMMING,
            company_id=create_company(name="Other Club").id,
            code="butterfly",
            name="Butterfly",
        )

    def test_list_excludes_other_company(
        self, client, create_exercise_option, other_option, auth_headers
    ):
        headers, _, company = auth_headers
        mine = create_exercise_option(
            segment_type=SegmentType.SWIMMING, company_id=company.id,
            code="free", name="Free",
        )

        response = _call(client, "get", "/api/exercise-option/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert mine.id in ids
        assert other_option.id not in ids

    def test_get_other_company_option_403(self, client, other_option, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "get", f"/api/exercise-option/{other_option.id}", headers)
        assert response.status_code == 403

    def test_super_admin_sees_other_company_option(
        self, client, other_option, super_admin_headers
    ):
        headers, _ = super_admin_headers
        response = _call(client, "get", f"/api/exercise-option/{other_option.id}", headers)
        assert response.status_code == 200
