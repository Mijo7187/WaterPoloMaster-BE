# ============================================
# EXERCISE OPTION - Sifarnik (reference data)
# ============================================
# A per-company, coach-maintained catalog of selectable exercises.
# Each option belongs to exactly one company and one SegmentType
# (SWIMMING / GYM / WORK_WITH_BALL). SPARRING has no catalog.
# Unique per (company_id, segment_type, code).
# ============================================

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum, ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base
from app.features.training_segments.training_segments_model import SegmentType


class ExerciseOption(Base):
    __tablename__ = "exercise_option"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "segment_type", "code",
            name="uq_exercise_option_company_segment_code",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    segment_type = Column(Enum(SegmentType, name="segmenttype"), nullable=False)
    code = Column(String(100), nullable=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company")

    def __repr__(self):
        return f"<ExerciseOption(id={self.id}, type='{self.segment_type}', code='{self.code}')>"
