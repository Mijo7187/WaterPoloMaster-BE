# ============================================
# TRAINING REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.training.training_model import Training
from app.features.training_users.training_users_model import TrainingUsers
from app.features.training_segments.training_segments_model import (
    SegmentExercise,
    SegmentSparring,
    TrainingSegment,
)


class TrainingRepository(CrudRepository[Training]):
    def __init__(self, db: Session):
        super().__init__(db, Training)

    def _apply_filter(self, q, key, value):
        # `user_id` is a virtual filter (no such column on training): match
        # trainings the user belongs to via the training_users join table.
        # Everything else falls through to the generic per-field filtering.
        if key == "user_id":
            return q.filter(
                Training.training_users.any(TrainingUsers.user_id == value)
            )
        return super()._apply_filter(q, key, value)

    def get_list_relations(self):
        return [
            lambda: selectinload(Training.company),
            lambda: selectinload(Training.pool),
            lambda: selectinload(Training.season),
            lambda: selectinload(Training.training_users),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Training.company),
            lambda: selectinload(Training.pool),
            lambda: selectinload(Training.season),
            lambda: selectinload(Training.training_users),
            lambda: selectinload(Training.segments)
            .selectinload(TrainingSegment.exercises)
            .selectinload(SegmentExercise.exercise_option),
            lambda: selectinload(Training.segments)
            .selectinload(TrainingSegment.sparring)
            .selectinload(SegmentSparring.events),
        ]
