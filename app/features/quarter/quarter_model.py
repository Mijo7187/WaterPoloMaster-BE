# ============================================
# QUARTER MODEL - Database Tables
# ============================================

import enum
from sqlalchemy import (
    Column, Integer, Numeric, DateTime, String, ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


# ============================================
# QUARTER TYPE ENUM
# ============================================
class QuarterType(str, enum.Enum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


# ============================================
# QUARTER MODEL
# ============================================
class Quarter(Base):
    __tablename__ = "quarter"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    quarter_type = Column(String(2), nullable=False)
    year = Column(Integer, nullable=False)
    waterpolo_price = Column(Numeric(10, 2), nullable=False)
    swimming_price = Column(Numeric(10, 2), nullable=False)
    description = Column(String(255), nullable=True)
    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    quarter_users = relationship("QuarterUsers", back_populates="quarter")

    @property
    def number_of_waterpolo_users(self) -> int:
        return sum(1 for qu in (self.quarter_users or []) if qu.type_of_training == "waterpolo")

    @property
    def number_of_swimming_users(self) -> int:
        return sum(1 for qu in (self.quarter_users or []) if qu.type_of_training == "swimming")

    def __repr__(self):
        return f"<Quarter(id={self.id}, quarter_type='{self.quarter_type}', year={self.year})>"
