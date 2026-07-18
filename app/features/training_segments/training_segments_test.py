# ============================================
# TRAINING SEGMENT TESTS
# ============================================

import pytest
from unittest.mock import patch

from app.core.api.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.features.training_segments.training_segments_model import EventType, SegmentType
from app.features.training_segments.training_segments_service import TrainingSegmentService
from app.features.training_segments.training_segments_schemas import (
    ExerciseSegmentCreate,
    SegmentExerciseCreate,
    SparringCreate,
    SparringEventCreate,
    SparringSegmentCreate,
    TrainingSegmentUpdate,
)
from app.features.users.users_models import UserRole


def _swimming(training_id, option_id, meters=800, **kwargs):
    return ExerciseSegmentCreate(
        training_id=training_id,
        segment_type=SegmentType.SWIMMING,
        duration_minutes=30,
        exercises=[SegmentExerciseCreate(exercise_option_id=option_id, meters=meters)],
        **kwargs,
    )


# ============================================
# CREATE
# ============================================

class TestSegmentCreate:

    def test_create_swimming_segment_assigns_position_and_exercises(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING)
        service = TrainingSegmentService(db_session)

        seg = service.create(_swimming(training.id, option.id, meters=1000))

        assert seg.id is not None
        assert seg.segment_type == SegmentType.SWIMMING
        assert seg.position == 1
        assert len(seg.exercises) == 1
        assert seg.exercises[0].meters == 1000
        assert seg.exercises[0].position == 1

    def test_positions_increment_per_training(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING)
        service = TrainingSegmentService(db_session)

        first = service.create(_swimming(training.id, option.id))
        second = service.create(_swimming(training.id, option.id))

        assert first.position == 1
        assert second.position == 2

    def test_create_gym_segment_requires_sets_and_reps(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.GYM, code="bench", name="Bench press")
        service = TrainingSegmentService(db_session)

        seg = service.create(ExerciseSegmentCreate(
            training_id=training.id,
            segment_type=SegmentType.GYM,
            exercises=[SegmentExerciseCreate(exercise_option_id=option.id, sets=3, reps=10, weight_kg=60)],
        ))
        assert seg.exercises[0].sets == 3
        assert seg.exercises[0].reps == 10

    def test_gym_missing_reps_raises(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.GYM, code="squat", name="Squat")
        service = TrainingSegmentService(db_session)

        with pytest.raises(BadRequestException, match="require"):
            service.create(ExerciseSegmentCreate(
                training_id=training.id,
                segment_type=SegmentType.GYM,
                exercises=[SegmentExerciseCreate(exercise_option_id=option.id, sets=3)],
            ))

    def test_exercise_option_type_mismatch_raises(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        gym_option = create_exercise_option(segment_type=SegmentType.GYM, code="bench", name="Bench")
        service = TrainingSegmentService(db_session)

        with pytest.raises(BadRequestException, match="cannot be used"):
            service.create(ExerciseSegmentCreate(
                training_id=training.id,
                segment_type=SegmentType.SWIMMING,
                exercises=[SegmentExerciseCreate(exercise_option_id=gym_option.id, meters=500)],
            ))

    def test_create_swimming_repeated_group(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        free = create_exercise_option(segment_type=SegmentType.SWIMMING, code="free", name="Freestyle")
        fly = create_exercise_option(segment_type=SegmentType.SWIMMING, code="fly", name="Butterfly")
        back = create_exercise_option(segment_type=SegmentType.SWIMMING, code="back", name="Backstroke")
        service = TrainingSegmentService(db_session)

        # 3 x (200 free + 200 fly + 100 back)
        seg = service.create(ExerciseSegmentCreate(
            training_id=training.id,
            segment_type=SegmentType.SWIMMING,
            exercises=[
                SegmentExerciseCreate(exercise_option_id=free.id, meters=200, sets=3, group_index=1),
                SegmentExerciseCreate(exercise_option_id=fly.id, meters=200, sets=3, group_index=1),
                SegmentExerciseCreate(exercise_option_id=back.id, meters=100, sets=3, group_index=1),
            ],
        ))

        assert len(seg.exercises) == 3
        assert [e.group_index for e in seg.exercises] == [1, 1, 1]
        assert [e.sets for e in seg.exercises] == [3, 3, 3]
        assert [e.position for e in seg.exercises] == [1, 2, 3]
        assert [e.meters for e in seg.exercises] == [200, 200, 100]

    def test_standalone_row_has_null_group_index(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING)
        service = TrainingSegmentService(db_session)

        seg = service.create(_swimming(training.id, option.id, meters=800))
        assert seg.exercises[0].group_index is None

    def test_group_with_mismatched_sets_raises(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        free = create_exercise_option(segment_type=SegmentType.SWIMMING, code="free", name="Freestyle")
        fly = create_exercise_option(segment_type=SegmentType.SWIMMING, code="fly", name="Butterfly")
        service = TrainingSegmentService(db_session)

        with pytest.raises(BadRequestException, match="same 'sets'"):
            service.create(ExerciseSegmentCreate(
                training_id=training.id,
                segment_type=SegmentType.SWIMMING,
                exercises=[
                    SegmentExerciseCreate(exercise_option_id=free.id, meters=200, sets=3, group_index=1),
                    SegmentExerciseCreate(exercise_option_id=fly.id, meters=200, sets=2, group_index=1),
                ],
            ))

    def test_create_sparring_segment_with_events(
        self, db_session, create_company, create_training, create_user
    ):
        company = create_company()
        opponent = create_company(name="Rivals")
        training = create_training(company_id=company.id)
        player = create_user(company_id=company.id)
        service = TrainingSegmentService(db_session)

        seg = service.create(SparringSegmentCreate(
            training_id=training.id,
            segment_type=SegmentType.SPARRING,
            sparring=SparringCreate(
                opponent_company_id=opponent.id,
                our_score=8,
                opponent_score=6,
                events=[SparringEventCreate(user_id=player.id, event_type=EventType.GOAL, minute=4)],
            ),
        ))

        assert seg.segment_type == SegmentType.SPARRING
        assert seg.sparring is not None
        assert seg.sparring.our_score == 8
        assert len(seg.sparring.events) == 1
        assert seg.sparring.events[0].event_type == EventType.GOAL

    def test_create_on_missing_training_raises(
        self, db_session, create_exercise_option
    ):
        option = create_exercise_option(segment_type=SegmentType.SWIMMING)
        service = TrainingSegmentService(db_session)
        with pytest.raises(NotFoundException):
            service.create(_swimming(999999, option.id))


# ============================================
# AUTHORIZATION (row-level company scope)
# ============================================

class TestSegmentAuthorization:

    def test_other_company_admin_forbidden(
        self, db_session, create_company, create_training, create_exercise_option, create_user
    ):
        company = create_company()
        other = create_company(name="Other")
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING)
        outsider = create_user(company_id=other.id, roles=[UserRole.ADMIN], email="a@b.c", username="outsider")
        service = TrainingSegmentService(db_session)

        with pytest.raises(ForbiddenException):
            service.create(_swimming(training.id, option.id), current_user=outsider)

    def test_super_admin_bypasses_company_scope(
        self, db_session, create_company, create_training, create_exercise_option, create_user
    ):
        company = create_company()
        other = create_company(name="Other")
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING)
        boss = create_user(company_id=other.id, roles=[UserRole.SUPER_ADMIN], email="s@b.c", username="boss")
        service = TrainingSegmentService(db_session)

        seg = service.create(_swimming(training.id, option.id), current_user=boss)
        assert seg.id is not None


# ============================================
# UPDATE / DELETE
# ============================================

class TestSegmentUpdateDelete:

    def test_update_scalar_fields_and_replace_exercises(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        o1 = create_exercise_option(segment_type=SegmentType.SWIMMING, code="free", name="Free")
        o2 = create_exercise_option(segment_type=SegmentType.SWIMMING, code="back", name="Back")
        service = TrainingSegmentService(db_session)
        seg = service.create(_swimming(training.id, o1.id, meters=500))

        updated = service.update(seg.id, TrainingSegmentUpdate(
            duration_minutes=45,
            notes="harder set",
            exercises=[
                SegmentExerciseCreate(exercise_option_id=o1.id, meters=800),
                SegmentExerciseCreate(exercise_option_id=o2.id, meters=400),
            ],
        ))
        assert updated.duration_minutes == 45
        assert updated.notes == "harder set"
        assert len(updated.exercises) == 2
        assert [e.position for e in updated.exercises] == [1, 2]

    def test_delete_does_not_reindex_positions(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING)
        service = TrainingSegmentService(db_session)
        s1 = service.create(_swimming(training.id, option.id))
        s2 = service.create(_swimming(training.id, option.id))
        s3 = service.create(_swimming(training.id, option.id))

        service.delete(s1.id)

        # remaining positions unchanged (gaps allowed)
        assert service.get_by_id(s2.id).position == 2
        assert service.get_by_id(s3.id).position == 3
        with pytest.raises(NotFoundException):
            service.get_by_id(s1.id)


# ============================================
# ENDPOINTS + NESTED READ
# ============================================

class TestSegmentEndpoints:

    def test_create_segment_and_read_nested_timeline(
        self, client, db_session, create_training, create_exercise_option, auth_headers
    ):
        headers, user, company = auth_headers
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING)

        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            resp = client.post("/api/training-segment/", json={
                "training_id": training.id,
                "segment_type": "SWIMMING",
                "duration_minutes": 30,
                "exercises": [{"exercise_option_id": option.id, "meters": 800}],
            }, headers=headers)
            assert resp.status_code == 201, resp.text
            assert resp.json()["data"]["position"] == 1

            # nested read via the training get-by-id
            got = client.get(f"/api/training/{training.id}", headers=headers)
            assert got.status_code == 200
            segments = got.json()["data"]["segments"]
            assert len(segments) == 1
            assert segments[0]["segment_type"] == "SWIMMING"
            assert segments[0]["exercises"][0]["meters"] == 800

    def test_create_segment_unauthenticated(self, client, db_session):
        resp = client.post("/api/training-segment/", json={
            "training_id": 1,
            "segment_type": "SWIMMING",
            "exercises": [],
        })
        assert resp.status_code in (401, 403)

    def test_list_segments_by_training(
        self, client, db_session, create_training, create_exercise_option, auth_headers
    ):
        headers, user, company = auth_headers
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING)

        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]

            client.post("/api/training-segment/", json={
                "training_id": training.id,
                "segment_type": "SWIMMING",
                "exercises": [{"exercise_option_id": option.id, "meters": 800}],
            }, headers=headers)
            client.post("/api/training-segment/", json={
                "training_id": training.id,
                "segment_type": "SWIMMING",
                "exercises": [{"exercise_option_id": option.id, "meters": 400}],
            }, headers=headers)

            resp = client.get(
                f"/api/training-segment/by-training/{training.id}", headers=headers
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()["data"]
            assert [s["position"] for s in data] == [1, 2]
            assert data[0]["exercises"][0]["meters"] == 800


# ============================================
# LIST BY TRAINING (service level)
# ============================================

class TestListByTraining:

    def test_returns_segments_ordered_with_children(
        self, db_session, create_company, create_training, create_exercise_option, create_user
    ):
        company = create_company()
        opponent = create_company(name="Rivals")
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING)
        player = create_user(company_id=company.id)
        service = TrainingSegmentService(db_session)

        swim = service.create(_swimming(training.id, option.id, meters=800))
        spar = service.create(SparringSegmentCreate(
            training_id=training.id,
            segment_type=SegmentType.SPARRING,
            sparring=SparringCreate(
                opponent_company_id=opponent.id,
                events=[SparringEventCreate(user_id=player.id, event_type=EventType.GOAL)],
            ),
        ))

        segments = service.list_by_training(training.id)
        assert [s.id for s in segments] == [swim.id, spar.id]
        assert [s.position for s in segments] == [1, 2]
        assert segments[0].exercises[0].meters == 800
        assert segments[1].sparring.events[0].event_type == EventType.GOAL

    def test_empty_training_returns_empty_list(
        self, db_session, create_company, create_training
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        service = TrainingSegmentService(db_session)
        assert service.list_by_training(training.id) == []

    def test_unknown_training_raises(self, db_session):
        service = TrainingSegmentService(db_session)
        with pytest.raises(NotFoundException):
            service.list_by_training(999999)
