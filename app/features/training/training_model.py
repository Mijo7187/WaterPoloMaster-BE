# ============================================
# TRAINING MODEL - Database Tables
# ============================================

import enum
from sqlalchemy import (
    Column, Integer, Numeric, DateTime, Date, Time, ForeignKey, String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base
from app.utils.dateUtils import quarter_type_for_date


# ============================================
# TRAINING STATUS ENUM
# ============================================
class TrainingStatus(str, enum.Enum):
    FINISHED = "FINISHED"
    IN_PROCESS = "IN_PROCESS"
    CANCELLED = "CANCELLED"
    INCOMING = "INCOMING"


# ============================================
# TRAINING MODEL
# ============================================
class Training(Base):
    __tablename__ = "training"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    training_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), default=TrainingStatus.INCOMING.value, nullable=False)
    pool_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("season.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    pool = relationship("Company", foreign_keys=[pool_id])
    season = relationship("Season")
    training_users = relationship("TrainingUsers", back_populates="training")
    segments = relationship(
        "TrainingSegment",
        back_populates="training",
        order_by="TrainingSegment.position",
        cascade="all, delete-orphan",
    )

    @property
    def number_of_players(self) -> int:
        return len(self.training_users or [])

    @property
    def quarter_type(self):
        """Calendar quarter label, derived from the date. There is no quarter
        table any more — the billing period is `season`."""
        return quarter_type_for_date(self.training_date) if self.training_date else None

    def __repr__(self):
        return f"<Training(id={self.id}, status='{self.status}')>"
