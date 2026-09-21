# ============================================
# TRAINING SEGMENT SERVICE - Business Logic
# ============================================
# Orchestrates segment writes in single transactions and enforces:
#   - the training exists and the caller is authorized on it (company scope)
#   - each chosen exercise_option's segment_type matches the segment's type
#   - per-type required metrics (swim->meters, gym->sets+reps, ball->reps)
#   - segment-level position assignment (max(position)+1; no reindex on delete)
# ============================================

from typing import List, Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.features.sifarnici.exercise_option.exercise_option_model import ExerciseOption
from app.features.training.training_model import Training
from app.features.training_segments.training_segments_model import (
    SegmentType,
    TrainingSegment,
)
from app.features.training_segments.training_segments_repository import TrainingSegmentRepository
from app.features.training_segments.training_segments_schemas import (
    ExerciseSegmentCreate,
    SegmentExerciseCreate,
    SparringSegmentCreate,
    TrainingSegmentUpdate,
)
from app.features.users.users_models import User, UserRole


# Which metric fields are required per exercise, keyed by the segment's type.
_REQUIRED_METRICS = {
    SegmentType.SWIMMING: ["meters"],
    SegmentType.GYM: ["sets", "reps"],
    SegmentType.WORK_WITH_BALL: ["reps"],
}


class TrainingSegmentService(CrudService[TrainingSegment]):
    def __init__(self, db: Session):
        super().__init__(db, TrainingSegmentRepository(db))
        self.repository: TrainingSegmentRepository = self.repository

    # ── Guards ──────────────────────────────────────

    def _get_training_or_404(self, training_id: int) -> Training:
        training = self.db.query(Training).filter(Training.id == training_id).first()
        if not training:
            raise NotFoundException("Training not found")
        return training

    def _authorize(self, training: Training, current_user: Optional[User]) -> None:
        # Internal calls (tests / scripts / jobs) are not gated here — HTTP auth
        # is enforced upstream. SUPER_ADMIN bypasses the company scope.
        if current_user is None:
            return
        if UserRole.SUPER_ADMIN.value in (current_user.roles or []):
            return
        if training.company_id != current_user.company_id:
            raise ForbiddenException(
                "You can only manage segments of trainings in your own company."
            )

    def list_by_training(self, training_id: int) -> List[TrainingSegment]:
        # 404 on an unknown training; reads are not company-scoped (matches get_by_id).
        self._get_training_or_404(training_id)
        return self.repository.get_by_training(training_id)

    def _get_segment_or_404(self, segment_id: int) -> TrainingSegment:
        segment = self.repository.get_by_id(segment_id)
        if not segment:
            raise NotFoundException("Training segment not found")
        return segment

    # ── Sparring validation ─────────────────────────

    @staticmethod
    def _field(row, name):
        # Rows arrive as Pydantic objects (create) or dicts (update).
        return row.get(name) if isinstance(row, dict) else getattr(row, name)

    def _validate_sparring_sides(self, participants, events) -> None:
        # A player-linked event must belong to a rostered participant and agree
        # on side. Opponent events (user_id=None) are unconstrained.
        side_by_user = {
            self._field(p, "user_id"): self._field(p, "side") for p in participants
        }
        for event in events:
            user_id = self._field(event, "user_id")
            if user_id is None:
                continue
            if user_id not in side_by_user:
                raise BadRequestException(
                    f"Event references user {user_id} who is not a sparring participant"
                )
            if side_by_user[user_id] != self._field(event, "side"):
                raise BadRequestException(
                    f"Event for user {user_id} has a side that does not match the "
                    f"player's participant side"
                )

    # ── Exercise validation / preparation ───────────

    def _validate_group_consistency(
        self, exercises: List[SegmentExerciseCreate]
    ) -> None:
        # Rows sharing a non-null group_index form one block repeated as a unit,
        # so they must agree on the repeat count (`sets`).
        sets_by_group: dict = {}
        for ex in exercises:
            if ex.group_index is None:
                continue
            if ex.group_index in sets_by_group:
                if sets_by_group[ex.group_index] != ex.sets:
                    raise BadRequestException(
                        f"Exercises in group {ex.group_index} must share the same "
                        f"'sets' value (the block repeats as a unit)"
                    )
            else:
                sets_by_group[ex.group_index] = ex.sets

    def _prepare_exercises(
        self, segment_type: SegmentType, exercises: List[SegmentExerciseCreate]
    ) -> List[dict]:
        self._validate_group_consistency(exercises)
        required = _REQUIRED_METRICS[segment_type]
        prepared: List[dict] = []
        for idx, ex in enumerate(exercises, start=1):
            option = (
                self.db.query(ExerciseOption)
                .filter(ExerciseOption.id == ex.exercise_option_id)
                .first()
            )
            if not option:
                raise BadRequestException(
                    f"Exercise option {ex.exercise_option_id} does not exist"
                )
            if option.segment_type != segment_type:
                raise BadRequestException(
                    f"Exercise option {ex.exercise_option_id} is a "
                    f"{option.segment_type.value} option and cannot be used in a "
                    f"{segment_type.value} segment"
                )
            missing = [m for m in required if getattr(ex, m) is None]
            if missing:
                raise BadRequestException(
                    f"{segment_type.value} exercises require: {', '.join(missing)}"
                )
            data = ex.model_dump()
            data["position"] = idx
            prepared.append(data)
        return prepared

    # ── CRUD ────────────────────────────────────────

    def create(self, schema, current_user: Optional[User] = None) -> TrainingSegment:
        training = self._get_training_or_404(schema.training_id)
        self._authorize(training, current_user)

        position = self.repository.get_max_position(schema.training_id) + 1
        segment_data = {
            "training_id": schema.training_id,
            "segment_type": schema.segment_type,
            "position": position,
            "duration_minutes": schema.duration_minutes,
            "notes": schema.notes,
        }

        if isinstance(schema, SparringSegmentCreate):
            self._validate_sparring_sides(
                schema.sparring.participants, schema.sparring.events
            )
            sparring_data = schema.sparring.model_dump(
                exclude={"participants", "events"}
            )
            participants = [p.model_dump() for p in schema.sparring.participants]
            events = [e.model_dump() for e in schema.sparring.events]
            return self.repository.create_sparring_segment(
                segment_data, sparring_data, participants, events
            )

        # Exercise segment (SWIMMING / GYM / WORK_WITH_BALL)
        assert isinstance(schema, ExerciseSegmentCreate)
        exercises = self._prepare_exercises(schema.segment_type, schema.exercises)
        return self.repository.create_exercise_segment(segment_data, exercises)

    def update(
        self, segment_id: int, schema: TrainingSegmentUpdate, current_user: Optional[User] = None
    ) -> TrainingSegment:
        segment = self._get_segment_or_404(segment_id)
        training = self._get_training_or_404(segment.training_id)
        self._authorize(training, current_user)

        data = schema.model_dump(exclude_unset=True)

        scalar_fields = {k: data[k] for k in ("duration_minutes", "notes") if k in data}
        if scalar_fields:
            self.repository.update_segment_fields(segment, scalar_fields)

        if "exercises" in data and data["exercises"] is not None:
            if segment.segment_type == SegmentType.SPARRING:
                raise BadRequestException("A sparring segment has no exercises")
            exercises = self._prepare_exercises(
                segment.segment_type,
                [SegmentExerciseCreate(**ex) for ex in data["exercises"]],
            )
            self.repository.replace_exercises(segment, exercises)

        if "sparring" in data and data["sparring"] is not None:
            if segment.segment_type != SegmentType.SPARRING:
                raise BadRequestException(
                    "Only a sparring segment can carry a sparring payload"
                )
            sparring_payload = data["sparring"]
            participants = sparring_payload.pop("participants", None)
            events = sparring_payload.pop("events", None)
            # Validate against the effective (post-update) lists: a list that is
            # not being replaced keeps its current rows.
            effective_participants = (
                participants
                if participants is not None
                else [
                    {"user_id": p.user_id, "side": p.side}
                    for p in segment.sparring.participants
                ]
            )
            effective_events = (
                events
                if events is not None
                else [
                    {"user_id": e.user_id, "side": e.side}
                    for e in segment.sparring.events
                ]
            )
            self._validate_sparring_sides(effective_participants, effective_events)
            self.repository.update_sparring(
                segment.sparring, sparring_payload, participants, events
            )

        return self.repository.commit_and_return(segment_id)

    def delete(self, segment_id: int, current_user: Optional[User] = None) -> None:
        segment = self._get_segment_or_404(segment_id)
        training = self._get_training_or_404(segment.training_id)
        self._authorize(training, current_user)
        # No position reindex — ordering is always ORDER BY position, gaps are fine.
        self.repository.delete(segment)
