# ============================================
# SWIMMING DISCIPLINE MODEL - Database Table
# ============================================

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class SwimmingDiscipline(Base):
    __tablename__ = "swimming_discipline"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)

    company = relationship("Company")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<SwimmingDiscipline(id={self.id}, name='{self.name}')>"
