# ============================================
# TRAINING SEGMENT SCHEMAS - Data Validation
# ============================================
# The create payload is a DISCRIMINATED UNION on `segment_type`:
#   - exercise segments (SWIMMING / GYM / WORK_WITH_BALL) carry an `exercises` list
#   - a SPARRING segment carries a `sparring` payload (with nested events)
#
# The DB stays flat; per-type semantic validation (which metric a given
# segment_type requires) lives in the service, which is the single source of
# truth for both create and update.
# ============================================

import re
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.company.company_schemas import CompanyResponse
from app.features.training_segments.training_segments_model import (
    EventType,
    SegmentType,
    SparringSide,
)

# Game-clock stamp, either "mm:ss" or "hh:mm:ss" (time-picker value).
# Seconds/minutes are 00-59; the leading unit (minutes or hours) is open-ended.
_CLOCK_RE = re.compile(r"^(?:\d{1,2}:[0-5]\d:[0-5]\d|\d{1,3}:[0-5]\d)$")


# ============================================
# CHILD CREATE SCHEMAS
# ============================================
class SegmentExerciseCreate(BaseModel):
    exercise_option_id: int
    position: Optional[int] = None  # backend assigns by list order when omitted
    group_index: Optional[int] = None  # rows sharing this form one repeated block
    meters: Optional[int] = None
    sets: Optional[int] = None  # repeat count of the row's block
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_seconds: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SparringEventCreate(BaseModel):
    # None = opponent action (opponent players are not in our users table).
    user_id: Optional[int] = None
    side: SparringSide  # which team the event counts for
    event_type: EventType
    # Game-clock stamp as "mm:ss" or "hh:mm:ss" (time-picker value), e.g. "07:30".
    minute: Optional[str] = None
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("minute")
    @classmethod
    def _validate_minute(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not _CLOCK_RE.match(v):
            raise ValueError(
                "minute must be a 'mm:ss' or 'hh:mm:ss' time string, e.g. '07:30'"
            )
        return v


class SparringParticipantCreate(BaseModel):
    user_id: int
    side: SparringSide

    model_config = ConfigDict(from_attributes=True)


class SparringCreate(BaseModel):
    # The two clubs. Internal sparring (us vs. us) may leave both null.
    # Scores are derived from side-tagged events, not stored.
    home_company_id: Optional[int] = None
    away_company_id: Optional[int] = None
    notes: Optional[str] = None
    participants: List[SparringParticipantCreate] = Field(default_factory=list)
    events: List[SparringEventCreate] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ============================================
# SEGMENT CREATE - discriminated union on segment_type
# ============================================
class _SegmentCreateBase(BaseModel):
    training_id: int
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ExerciseSegmentCreate(_SegmentCreateBase):
    segment_type: Literal[
        SegmentType.SWIMMING, SegmentType.GYM, SegmentType.WORK_WITH_BALL
    ]
    exercises: List[SegmentExerciseCreate] = Field(default_factory=list)


class SparringSegmentCreate(_SegmentCreateBase):
    segment_type: Literal[SegmentType.SPARRING]
    sparring: SparringCreate


# Discriminated union alias used as the request body (see router).
TrainingSegmentCreate = Annotated[
    Union[ExerciseSegmentCreate, SparringSegmentCreate],
    Field(discriminator="segment_type"),
]


# ============================================
# SEGMENT UPDATE (segment_type is not changeable)
# ============================================
class SparringUpdate(BaseModel):
    home_company_id: Optional[int] = None
    away_company_id: Optional[int] = None
    notes: Optional[str] = None
    # When provided, each fully replaces its respective list.
    participants: Optional[List[SparringParticipantCreate]] = None
    events: Optional[List[SparringEventCreate]] = None

    model_config = ConfigDict(from_attributes=True)


class TrainingSegmentUpdate(BaseModel):
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    # When provided on an exercise segment, fully replaces the exercise rows.
    exercises: Optional[List[SegmentExerciseCreate]] = None
    # When provided on a sparring segment, updates the sparring detail.
    sparring: Optional[SparringUpdate] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================
# RESPONSE SCHEMAS (nested — reused by the training nested read)
# ============================================
class ExerciseOptionMini(BaseModel):
    id: int
    segment_type: SegmentType
    code: Optional[str] = None  # code is nullable on exercise_option
    name: str

    model_config = ConfigDict(from_attributes=True)


class SegmentExerciseResponse(BaseModel):
    id: int
    exercise_option_id: int
    position: int
    group_index: Optional[int] = None
    meters: Optional[int] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_seconds: Optional[int] = None
    exercise_option: Optional[ExerciseOptionMini] = None

    model_config = ConfigDict(from_attributes=True)


class SparringEventResponse(BaseModel):
    id: int
    user_id: Optional[int] = None  # None = opponent action
    side: Optional[SparringSide] = None
    event_type: EventType
    minute: Optional[str] = None  # "mm:ss" game-clock stamp
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SparringParticipantResponse(BaseModel):
    id: int
    user_id: int
    side: SparringSide

    model_config = ConfigDict(from_attributes=True)


class SegmentSparringResponse(BaseModel):
    id: int
    home_company_id: Optional[int] = None
    away_company_id: Optional[int] = None
    # Nested full company objects (null for internal sparring with no club set).
    home_company: Optional[CompanyResponse] = None
    away_company: Optional[CompanyResponse] = None
    notes: Optional[str] = None
    participants: List[SparringParticipantResponse] = Field(default_factory=list)
    events: List[SparringEventResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TrainingSegmentResponse(BaseModel):
    id: int
    training_id: int
    segment_type: SegmentType
    position: int
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    exercises: List[SegmentExerciseResponse] = Field(default_factory=list)
    sparring: Optional[SegmentSparringResponse] = None

    model_config = ConfigDict(from_attributes=True)
