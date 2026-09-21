# ============================================
# TRAINING SEGMENT REPOSITORY - Database Operations
# ============================================
# All SQLAlchemy for the segment bounded context lives here: the timeline
# rows and their per-type detail (exercises / sparring + events). The service
# passes validated primitives; this layer builds and persists the ORM graph.
# ============================================

from typing import List, Optional

from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import func

from app.common.crud.crud_repository import CrudRepository
from app.features.company.company_model import Company
from app.features.training_segments.training_segments_model import (
    SegmentExercise,
    SegmentSparring,
    SparringEvent,
    SparringParticipant,
    TrainingSegment,
)


class TrainingSegmentRepository(CrudRepository[TrainingSegment]):
    def __init__(self, db: Session):
        super().__init__(db, TrainingSegment)

    def get_by_id_relations(self):
        return [
            lambda: selectinload(TrainingSegment.exercises).selectinload(
                SegmentExercise.exercise_option
            ),
            lambda: selectinload(TrainingSegment.sparring).selectinload(
                SegmentSparring.events
            ),
            lambda: selectinload(TrainingSegment.sparring).selectinload(
                SegmentSparring.participants
            ),
            # Full nested company objects on the sparring detail (home/away),
            # with their city/country/wallet so CompanyResponse serializes
            # without per-row lazy loads.
            lambda: selectinload(TrainingSegment.sparring)
            .selectinload(SegmentSparring.home_company)
            .selectinload(Company.city),
            lambda: selectinload(TrainingSegment.sparring)
            .selectinload(SegmentSparring.home_company)
            .selectinload(Company.country),
            lambda: selectinload(TrainingSegment.sparring)
            .selectinload(SegmentSparring.home_company)
            .selectinload(Company.wallet),
            lambda: selectinload(TrainingSegment.sparring)
            .selectinload(SegmentSparring.away_company)
            .selectinload(Company.city),
            lambda: selectinload(TrainingSegment.sparring)
            .selectinload(SegmentSparring.away_company)
            .selectinload(Company.country),
            lambda: selectinload(TrainingSegment.sparring)
            .selectinload(SegmentSparring.away_company)
            .selectinload(Company.wallet),
        ]

    # ── Helpers ─────────────────────────────────────

    def get_by_training(self, training_id: int) -> List[TrainingSegment]:
        query = self.db.query(TrainingSegment).filter(
            TrainingSegment.training_id == training_id
        )
        for relation in self.get_by_id_relations():
            query = query.options(relation())
        return query.order_by(TrainingSegment.position).all()

    def get_max_position(self, training_id: int) -> int:
        value = (
            self.db.query(func.max(TrainingSegment.position))
            .filter(TrainingSegment.training_id == training_id)
            .scalar()
        )
        return value or 0

    # ── Aggregate writes (segment + detail, one transaction) ──

    def create_exercise_segment(
        self, segment_data: dict, exercises: List[dict]
    ) -> TrainingSegment:
        segment = TrainingSegment(**segment_data)
        for ex in exercises:
            segment.exercises.append(SegmentExercise(**ex))
        self.db.add(segment)
        self.db.commit()
        return self.get_by_id(segment.id)

    def create_sparring_segment(
        self,
        segment_data: dict,
        sparring_data: dict,
        participants: List[dict],
        events: List[dict],
    ) -> TrainingSegment:
        segment = TrainingSegment(**segment_data)
        sparring = SegmentSparring(**sparring_data)
        for participant in participants:
            sparring.participants.append(SparringParticipant(**participant))
        for event in events:
            sparring.events.append(SparringEvent(**event))
        segment.sparring = sparring
        self.db.add(segment)
        self.db.commit()
        return self.get_by_id(segment.id)

    def update_segment_fields(self, segment: TrainingSegment, fields: dict) -> None:
        for key, value in fields.items():
            setattr(segment, key, value)

    def replace_exercises(self, segment: TrainingSegment, exercises: List[dict]) -> None:
        segment.exercises = [SegmentExercise(**ex) for ex in exercises]

    def update_sparring(
        self,
        sparring: SegmentSparring,
        fields: dict,
        participants: Optional[List[dict]],
        events: Optional[List[dict]],
    ) -> None:
        for key, value in fields.items():
            setattr(sparring, key, value)
        if participants is not None:
            # Clear + flush the old rows before inserting the new roster.
            # participant has a UNIQUE(segment_sparring_id, user_id); the unit of
            # work emits INSERTs before DELETEs in a single flush, so a re-sent
            # user would collide with its own still-present row. Flushing the
            # deletes first avoids the false unique violation.
            sparring.participants = []
            self.db.flush()
            sparring.participants = [
                SparringParticipant(**participant) for participant in participants
            ]
        if events is not None:
            sparring.events = [SparringEvent(**event) for event in events]

    def commit_and_return(self, segment_id: int) -> TrainingSegment:
        self.db.commit()
        return self.get_by_id(segment_id)

    def delete(self, segment: TrainingSegment) -> None:
        self.db.delete(segment)
        self.db.commit()
