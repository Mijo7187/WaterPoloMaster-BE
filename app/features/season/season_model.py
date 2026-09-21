# ============================================
# SEASON MODEL - Database Tables
# ============================================
# A season is a club's billing/competition period (e.g. "2025/26").
# It replaces the old `quarter` table as the period trainings and
# tournaments hang off; the Q1-Q4 label is now derived from the date
# (see app/utils/dateUtils.quarter_type_for_date), not stored.
# ============================================

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class Season(Base):
    __tablename__ = "season"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_current = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company")

    def __repr__(self):
        return f"<Season(id={self.id}, name='{self.name}', is_current={self.is_current})>"
