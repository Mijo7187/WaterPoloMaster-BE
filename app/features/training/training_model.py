# ============================================
# TRAINING MODEL - Database Tables
# ============================================

import enum
from sqlalchemy import (
    Column, Integer, Numeric, Boolean, DateTime, ForeignKey, Table, String,
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
# MANY-TO-MANY: training <-> users
# ============================================
training_users = Table(
    "training_users",
    Base.metadata,
    Column("training_id", Integer, ForeignKey("training.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


# ============================================
# TRAINING MODEL
# ============================================
class Training(Base):
    __tablename__ = "training"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    start_training_date_time = Column(DateTime(timezone=True), nullable=False)
    end_training_date_time = Column(DateTime(timezone=True), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    payed = Column(Boolean, default=False)
    status = Column(String(20), default=TrainingStatus.INCOMING.value, nullable=False)
    pool_id = Column(Integer, ForeignKey("company.id"), nullable=True)


    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    users = relationship("User", secondary=training_users)
    pool = relationship("Company", foreign_keys=[pool_id])

    def __repr__(self):
        return f"<Training(id={self.id}, status='{self.status}')>"
