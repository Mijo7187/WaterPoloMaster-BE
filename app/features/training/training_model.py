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
    training_type_id = Column(Integer, ForeignKey("training_type.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    pool = relationship("Company", foreign_keys=[pool_id])
    training_type = relationship("TrainingType")
    training_users_list = relationship("TrainingUsersList", back_populates="training")

    @property
    def number_of_players(self) -> int:
        return len(self.training_users_list or [])

    def __repr__(self):
        return f"<Training(id={self.id}, status='{self.status}')>"
