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

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from app.features.training_segments.training_segments_model import EventType, SegmentType


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
    user_id: int
    event_type: EventType
    minute: Optional[int] = None
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SparringCreate(BaseModel):
    opponent_company_id: int
    our_score: Optional[int] = None
    opponent_score: Optional[int] = None
    notes: Optional[str] = None
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
    opponent_company_id: Optional[int] = None
    our_score: Optional[int] = None
    opponent_score: Optional[int] = None
    notes: Optional[str] = None
    # When provided, fully replaces the event list.
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
    code: str
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
    user_id: int
    event_type: EventType
    minute: Optional[int] = None
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SegmentSparringResponse(BaseModel):
    id: int
    opponent_company_id: int
    our_score: Optional[int] = None
    opponent_score: Optional[int] = None
    notes: Optional[str] = None
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
