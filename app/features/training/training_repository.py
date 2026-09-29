# ============================================
# TRAINING REPOSITORY - Database Operations
# ============================================

from decimal import Decimal
from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.group.group_model import Group
from app.features.training.training_model import Training, TrainingStatus
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

    def get_summary(self, filters, company_id=None) -> Optional[dict]:
        q = self.list_query(filters, company_id)

        by_status = {s.value: 0 for s in TrainingStatus}
        for status, n in (
            q.with_entities(Training.status, func.count(Training.id))
            .group_by(Training.status)
            .all()
        ):
            by_status[status] = n

        total_price = q.with_entities(
            func.coalesce(
                func.sum(
                    case((Training.status != TrainingStatus.CANCELLED.value, Training.price), else_=0)
                ),
                0,
            )
        ).scalar()

        return {
            "count": sum(by_status.values()),
            "by_status": by_status,
            "total_price": Decimal(str(total_price or 0)),
        }

    def get_list_relations(self):
        return [
            lambda: selectinload(Training.company),
            lambda: selectinload(Training.pool),
            lambda: selectinload(Training.season),
            lambda: selectinload(Training.training_users),
            # Chained: the list response prints the squad's selection name.
            lambda: selectinload(Training.group).selectinload(Group.selection),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Training.company),
            lambda: selectinload(Training.pool),
            lambda: selectinload(Training.season),
            lambda: selectinload(Training.training_users),
            lambda: selectinload(Training.group).selectinload(Group.selection),
            lambda: selectinload(Training.group).selectinload(Group.season),
            lambda: selectinload(Training.segments)
            .selectinload(TrainingSegment.exercises)
            .selectinload(SegmentExercise.exercise_option),
            lambda: selectinload(Training.segments)
            .selectinload(TrainingSegment.sparring)
            .selectinload(SegmentSparring.events),
        ]
