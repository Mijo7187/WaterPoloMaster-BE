# ============================================
# SELECTION MODEL - Reference Data
# ============================================
# A selection is an age/skill group a club runs (U15, U16, Masters, ...).
# Stable identity across seasons. There is deliberately NO price here —
# pricing lives on `membership`, which is a flat per-company catalog and
# is not tied to a selection or a season.
# ============================================

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class Selection(Base):
    __tablename__ = "selection"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_selection_company_name"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    name = Column(String(100), nullable=False)
    age_min = Column(Integer, nullable=True)
    age_max = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company")

    def __repr__(self):
        return f"<Selection(id={self.id}, name='{self.name}')>"
