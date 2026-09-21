# ============================================
# TRAINING SEGMENTS - Database Tables
# ============================================
# One training is an ordered sequence of segments (the timeline).
# Type-specific detail hangs off each segment:
#   - SWIMMING / GYM / WORK_WITH_BALL -> segment_exercise rows
#   - SPARRING                        -> one segment_sparring (+ sparring_event rows)
#
# All four segment-domain tables live in this one file on purpose: they are a
# single bounded context, written and read together through one router/service.
# ============================================

import enum
from sqlalchemy import (
    Column, Integer, Numeric, DateTime, Text, String, ForeignKey, Enum,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


# ============================================
# ENUMS
# ============================================
class SegmentType(str, enum.Enum):
    SWIMMING = "SWIMMING"
    SPARRING = "SPARRING"
    GYM = "GYM"
    WORK_WITH_BALL = "WORK_WITH_BALL"


class EventType(str, enum.Enum):
    GOAL = "GOAL"
    ASSIST = "ASSIST"
    SAVE = "SAVE"
    EXCLUSION = "EXCLUSION"
    PENALTY = "PENALTY"


class SparringSide(str, enum.Enum):
    HOME = "HOME"
    AWAY = "AWAY"


# ============================================
# TRAINING SEGMENT - the timeline row
# ============================================
class TrainingSegment(Base):
    __tablename__ = "training_segment"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    training_id = Column(
        Integer, ForeignKey("training.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_type = Column(Enum(SegmentType, name="segmenttype"), nullable=False)
    position = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    training = relationship("Training", back_populates="segments")
    exercises = relationship(
        "SegmentExercise",
        back_populates="segment",
        order_by="SegmentExercise.position",
        cascade="all, delete-orphan",
    )
    sparring = relationship(
        "SegmentSparring",
        back_populates="segment",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<TrainingSegment(id={self.id}, type='{self.segment_type}', pos={self.position})>"


# ============================================
# SEGMENT EXERCISE - filled rows for SWIMMING / GYM / WORK_WITH_BALL
# ============================================
class SegmentExercise(Base):
    __tablename__ = "segment_exercise"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    segment_id = Column(
        Integer, ForeignKey("training_segment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_option_id = Column(Integer, ForeignKey("exercise_option.id"), nullable=False)
    position = Column(Integer, nullable=False)

    # Groups rows into a repeated block within the segment. Rows sharing a
    # non-null group_index (and the same `sets` value) form one block repeated
    # `sets` times, e.g. 3 x (200 free + 200 fly + 100 back). Null = standalone.
    group_index = Column(Integer, nullable=True)

    # Per-type metric columns (all nullable — used depending on segment_type)
    meters = Column(Integer, nullable=True)            # swimming
    sets = Column(Integer, nullable=True)              # gym / block-repeat count
    reps = Column(Integer, nullable=True)              # gym / ball
    weight_kg = Column(Numeric(6, 2), nullable=True)   # gym
    duration_seconds = Column(Integer, nullable=True)  # any

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    segment = relationship("TrainingSegment", back_populates="exercises")
    exercise_option = relationship("ExerciseOption")

    def __repr__(self):
        return f"<SegmentExercise(id={self.id}, segment_id={self.segment_id})>"


# ============================================
# SEGMENT SPARRING - one-to-one with a SPARRING segment
# ============================================
class SegmentSparring(Base):
    __tablename__ = "segment_sparring"
    __table_args__ = (UniqueConstraint("segment_id"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    segment_id = Column(
        Integer, ForeignKey("training_segment.id", ondelete="CASCADE"), nullable=False
    )
    # The two clubs that met. Nullable: internal sparring (us vs. us) may leave
    # both null or point both at our own club. side HOME -> home_company_id,
    # side AWAY -> away_company_id. Scores are derived from side-tagged events,
    # not stored.
    home_company_id = Column(Integer, ForeignKey("company.id"), nullable=True)
    away_company_id = Column(Integer, ForeignKey("company.id"), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    segment = relationship("TrainingSegment", back_populates="sparring")
    home_company = relationship("Company", foreign_keys=[home_company_id])
    away_company = relationship("Company", foreign_keys=[away_company_id])
    events = relationship(
        "SparringEvent",
        back_populates="sparring",
        cascade="all, delete-orphan",
    )
    participants = relationship(
        "SparringParticipant",
        back_populates="sparring",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<SegmentSparring(id={self.id}, segment_id={self.segment_id})>"


# ============================================
# SPARRING PARTICIPANT - roster: our players + their side (HOME / AWAY)
# ============================================
# One row per our-club player per sparring. For internal sparring the squad is
# split across HOME and AWAY; for external play our players share one side and
# the opponent (untracked per-player) is the other. Opponents are never
# participants (they are not in our `users` table).
class SparringParticipant(Base):
    __tablename__ = "sparring_participant"
    __table_args__ = (UniqueConstraint("segment_sparring_id", "user_id"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    segment_sparring_id = Column(
        Integer, ForeignKey("segment_sparring.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    side = Column(Enum(SparringSide, name="sparringside"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sparring = relationship("SegmentSparring", back_populates="participants")
    user = relationship("User")

    def __repr__(self):
        return f"<SparringParticipant(id={self.id}, user_id={self.user_id}, side='{self.side}')>"


# ============================================
# SPARRING EVENT - per-player match events
# ============================================
class SparringEvent(Base):
    __tablename__ = "sparring_event"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    segment_sparring_id = Column(
        Integer, ForeignKey("segment_sparring.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # None = opponent action (opponents are not in our `users` table).
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Which team the event counts for. DB-nullable for pre-existing rows; the
    # create schema requires it.
    side = Column(Enum(SparringSide, name="sparringside"), nullable=True)
    event_type = Column(Enum(EventType, name="eventtype"), nullable=False)
    # Game-clock stamp of the event as "mm:ss" or "hh:mm:ss" (time-picker value), not an int.
    minute = Column(String(8), nullable=True)
    note = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sparring = relationship("SegmentSparring", back_populates="events")
    user = relationship("User")

    def __repr__(self):
        return f"<SparringEvent(id={self.id}, type='{self.event_type}', user_id={self.user_id})>"
