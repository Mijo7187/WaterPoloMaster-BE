# ============================================
# EXERCISE OPTION (sifarnik) TESTS
# ============================================

import pytest
from unittest.mock import patch

from app.features.sifarnici.exercise_option.exercise_option_repository import ExerciseOptionRepository
from app.features.sifarnici.exercise_option.exercise_option_schemas import ExerciseOptionFilters
from app.features.training_segments.training_segments_model import SegmentType


class TestExerciseOptionRepository:

    def test_create_and_get(self, db_session):
        repo = ExerciseOptionRepository(db_session)
        option = repo.create({
            "segment_type": SegmentType.SWIMMING,
            "code": "freestyle",
            "name": "Freestyle",
            "is_active": True,
        })
        assert option.id is not None
        assert repo.get_by_id(option.id).code == "freestyle"

    def test_filter_by_segment_type(self, db_session, create_exercise_option):
        create_exercise_option(segment_type=SegmentType.SWIMMING, code="free", name="Free")
        create_exercise_option(segment_type=SegmentType.GYM, code="bench", name="Bench")
        repo = ExerciseOptionRepository(db_session)

        items, total = repo.get_list(filters=ExerciseOptionFilters(segment_type=SegmentType.GYM))
        assert total == 1
        assert items[0].code == "bench"

    def test_unique_segment_type_code(self, db_session, create_exercise_option):
        create_exercise_option(segment_type=SegmentType.SWIMMING, code="free", name="Free")
        with pytest.raises(Exception):
            create_exercise_option(segment_type=SegmentType.SWIMMING, code="free", name="Dup")


class TestExerciseOptionEndpoints:

    def test_create_and_list_endpoint(self, client, db_session, auth_headers):
        headers, user, company = auth_headers
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            resp = client.post("/api/exercise-option/", json={
                "segment_type": "WORK_WITH_BALL",
                "code": "passing",
                "name": "Passing drill",
            }, headers=headers)
            assert resp.status_code == 201, resp.text

            listed = client.get("/api/exercise-option/", headers=headers)
            assert listed.status_code == 200
            assert isinstance(listed.json()["data"]["items"], list)
