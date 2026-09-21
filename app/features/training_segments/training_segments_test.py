# ============================================
# TRAINING SEGMENT TESTS
# ============================================

import pytest
from unittest.mock import patch

from app.core.api.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.features.training_segments.training_segments_model import (
    EventType,
    SegmentType,
    SparringSide,
)
from app.features.training_segments.training_segments_service import TrainingSegmentService
from app.features.training_segments.training_segments_schemas import (
    ExerciseSegmentCreate,
    SegmentExerciseCreate,
    SparringCreate,
    SparringEventCreate,
    SparringParticipantCreate,
    SparringSegmentCreate,
    SparringUpdate,
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
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id)
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
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id)
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
        option = create_exercise_option(segment_type=SegmentType.GYM, company_id=company.id, code="bench", name="Bench press")
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
        option = create_exercise_option(segment_type=SegmentType.GYM, company_id=company.id, code="squat", name="Squat")
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
        gym_option = create_exercise_option(segment_type=SegmentType.GYM, company_id=company.id, code="bench", name="Bench")
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
        free = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code="free", name="Freestyle")
        fly = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code="fly", name="Butterfly")
        back = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code="back", name="Backstroke")
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
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id)
        service = TrainingSegmentService(db_session)

        seg = service.create(_swimming(training.id, option.id, meters=800))
        assert seg.exercises[0].group_index is None

    def test_group_with_mismatched_sets_raises(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        free = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code="free", name="Freestyle")
        fly = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code="fly", name="Butterfly")
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
                home_company_id=company.id,
                away_company_id=opponent.id,
                participants=[SparringParticipantCreate(user_id=player.id, side=SparringSide.HOME)],
                events=[SparringEventCreate(
                    user_id=player.id, side=SparringSide.HOME, event_type=EventType.GOAL, minute="04:00"
                )],
            ),
        ))

        assert seg.segment_type == SegmentType.SPARRING
        assert seg.sparring is not None
        assert seg.sparring.home_company_id == company.id
        assert seg.sparring.away_company_id == opponent.id
        assert len(seg.sparring.participants) == 1
        assert seg.sparring.participants[0].side == SparringSide.HOME
        assert len(seg.sparring.events) == 1
        assert seg.sparring.events[0].event_type == EventType.GOAL
        assert seg.sparring.events[0].side == SparringSide.HOME
        # minute is stored/returned as the "mm:ss" time-picker string, not an int.
        assert seg.sparring.events[0].minute == "04:00"

    def test_sparring_event_minute_rejects_non_mmss(self):
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SparringEventCreate(
                side=SparringSide.HOME, event_type=EventType.GOAL, minute="4"
            )

    def test_create_internal_sparring_without_opponent(
        self, db_session, create_company, create_training, create_user
    ):
        # Internal sparring (us vs. us): no opponent company. The squad is split
        # across HOME and AWAY; events are attributed to a player's side.
        company = create_company()
        training = create_training(company_id=company.id)
        home_player = create_user(company_id=company.id, email="h@b.c", username="home")
        away_player = create_user(company_id=company.id, email="a@b.c", username="away")
        service = TrainingSegmentService(db_session)

        seg = service.create(SparringSegmentCreate(
            training_id=training.id,
            segment_type=SegmentType.SPARRING,
            sparring=SparringCreate(
                participants=[
                    SparringParticipantCreate(user_id=home_player.id, side=SparringSide.HOME),
                    SparringParticipantCreate(user_id=away_player.id, side=SparringSide.AWAY),
                ],
                events=[
                    SparringEventCreate(user_id=home_player.id, side=SparringSide.HOME, event_type=EventType.GOAL),
                    SparringEventCreate(user_id=away_player.id, side=SparringSide.AWAY, event_type=EventType.GOAL),
                ],
            ),
        ))

        assert seg.sparring.home_company_id is None
        assert seg.sparring.away_company_id is None
        assert {p.side for p in seg.sparring.participants} == {SparringSide.HOME, SparringSide.AWAY}
        assert len(seg.sparring.events) == 2
        sides = {e.user_id: e.side for e in seg.sparring.events}
        assert sides[home_player.id] == SparringSide.HOME
        assert sides[away_player.id] == SparringSide.AWAY

    def test_create_sparring_with_opponent_event_no_user(
        self, db_session, create_company, create_training, create_user
    ):
        # External sparring: an opponent goal has no user_id (opponents aren't in
        # our users table) — it is recorded as an AWAY event with user_id=None.
        company = create_company()
        opponent = create_company(name="Rivals")
        training = create_training(company_id=company.id)
        player = create_user(company_id=company.id)
        service = TrainingSegmentService(db_session)

        seg = service.create(SparringSegmentCreate(
            training_id=training.id,
            segment_type=SegmentType.SPARRING,
            sparring=SparringCreate(
                home_company_id=company.id,
                away_company_id=opponent.id,
                participants=[SparringParticipantCreate(user_id=player.id, side=SparringSide.HOME)],
                events=[
                    SparringEventCreate(user_id=player.id, side=SparringSide.HOME, event_type=EventType.GOAL),
                    SparringEventCreate(user_id=None, side=SparringSide.AWAY, event_type=EventType.GOAL),
                ],
            ),
        ))

        opponent_events = [e for e in seg.sparring.events if e.user_id is None]
        assert len(opponent_events) == 1
        assert opponent_events[0].side == SparringSide.AWAY

    def test_event_side_must_match_participant_side(
        self, db_session, create_company, create_training, create_user
    ):
        # A player-linked event whose side contradicts the player's roster side
        # is rejected.
        company = create_company()
        training = create_training(company_id=company.id)
        player = create_user(company_id=company.id)
        service = TrainingSegmentService(db_session)

        with pytest.raises(BadRequestException, match="does not match"):
            service.create(SparringSegmentCreate(
                training_id=training.id,
                segment_type=SegmentType.SPARRING,
                sparring=SparringCreate(
                    participants=[SparringParticipantCreate(user_id=player.id, side=SparringSide.HOME)],
                    events=[SparringEventCreate(
                        user_id=player.id, side=SparringSide.AWAY, event_type=EventType.GOAL
                    )],
                ),
            ))

    def test_event_user_must_be_a_participant(
        self, db_session, create_company, create_training, create_user
    ):
        # A player-linked event for someone not on the roster is rejected.
        company = create_company()
        training = create_training(company_id=company.id)
        player = create_user(company_id=company.id)
        service = TrainingSegmentService(db_session)

        with pytest.raises(BadRequestException, match="not a sparring participant"):
            service.create(SparringSegmentCreate(
                training_id=training.id,
                segment_type=SegmentType.SPARRING,
                sparring=SparringCreate(
                    participants=[],
                    events=[SparringEventCreate(
                        user_id=player.id, side=SparringSide.HOME, event_type=EventType.GOAL
                    )],
                ),
            ))

    def test_create_on_missing_training_raises(
        self, db_session, create_company, create_exercise_option
    ):
        company = create_company()
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id)
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
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id)
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
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id)
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
        o1 = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code="free", name="Free")
        o2 = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code="back", name="Back")
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

    def test_response_includes_exercise_option_when_code_is_null(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        # Regression: exercise_option.code is nullable. A null code must not break
        # response serialization — the nested exercise_option object must still come
        # through (ExerciseOptionMini.code is Optional).
        from app.features.training_segments.training_segments_schemas import (
            TrainingSegmentResponse,
        )

        company = create_company()
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id, code=None)
        service = TrainingSegmentService(db_session)

        seg = service.create(_swimming(training.id, option.id, meters=800))
        dumped = TrainingSegmentResponse.model_validate(seg).model_dump()

        exercise_option = dumped["exercises"][0]["exercise_option"]
        assert exercise_option is not None
        assert exercise_option["id"] == option.id
        assert exercise_option["code"] is None
        assert exercise_option["name"] == option.name

    def test_delete_does_not_reindex_positions(
        self, db_session, create_company, create_training, create_exercise_option
    ):
        company = create_company()
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id)
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

    def test_update_sparring_roster_keeps_existing_participant(
        self, db_session, create_company, create_training, create_user
    ):
        # Regression: replacing the roster with a payload that re-sends an
        # already-rostered player must not trip the
        # UNIQUE(segment_sparring_id, user_id) constraint. The unit of work emits
        # INSERTs before DELETEs in one flush, so the old row must be flushed out
        # before the re-sent row is inserted.
        company = create_company()
        training = create_training(company_id=company.id)
        p1 = create_user(company_id=company.id, email="p1@b.c", username="p1")
        p2 = create_user(company_id=company.id, email="p2@b.c", username="p2")
        p3 = create_user(company_id=company.id, email="p3@b.c", username="p3")
        service = TrainingSegmentService(db_session)

        seg = service.create(SparringSegmentCreate(
            training_id=training.id,
            segment_type=SegmentType.SPARRING,
            sparring=SparringCreate(
                participants=[
                    SparringParticipantCreate(user_id=p1.id, side=SparringSide.HOME),
                    SparringParticipantCreate(user_id=p2.id, side=SparringSide.AWAY),
                ],
            ),
        ))

        # p1 stays (re-sent), p2 dropped, p3 added.
        updated = service.update(seg.id, TrainingSegmentUpdate(
            sparring=SparringUpdate(
                participants=[
                    SparringParticipantCreate(user_id=p1.id, side=SparringSide.HOME),
                    SparringParticipantCreate(user_id=p3.id, side=SparringSide.HOME),
                ],
            ),
        ))

        roster = {p.user_id: p.side for p in updated.sparring.participants}
        assert roster == {p1.id: SparringSide.HOME, p3.id: SparringSide.HOME}


# ============================================
# ENDPOINTS + NESTED READ
# ============================================

class TestSegmentEndpoints:

    def test_create_segment_and_read_nested_timeline(
        self, client, db_session, create_training, create_exercise_option, auth_headers
    ):
        headers, user, company = auth_headers
        training = create_training(company_id=company.id)
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id)

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
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id)

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
        option = create_exercise_option(segment_type=SegmentType.SWIMMING, company_id=company.id)
        player = create_user(company_id=company.id)
        service = TrainingSegmentService(db_session)

        swim = service.create(_swimming(training.id, option.id, meters=800))
        spar = service.create(SparringSegmentCreate(
            training_id=training.id,
            segment_type=SegmentType.SPARRING,
            sparring=SparringCreate(
                home_company_id=company.id,
                away_company_id=opponent.id,
                participants=[SparringParticipantCreate(user_id=player.id, side=SparringSide.HOME)],
                events=[SparringEventCreate(
                    user_id=player.id, side=SparringSide.HOME, event_type=EventType.GOAL
                )],
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
