# ============================================
# QUARTER MODEL - Database Tables
# ============================================

import enum
from datetime import date
from sqlalchemy import (
    Column, Integer, Numeric, DateTime, String, ForeignKey, Enum,
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


def quarter_type_for_date(d: date) -> QuarterType:
    """Map a calendar date to its quarter: Jan-Mar=Q1, Apr-Jun=Q2, Jul-Sep=Q3, Oct-Dec=Q4."""
    return {
        1: QuarterType.Q1, 2: QuarterType.Q1, 3: QuarterType.Q1,
        4: QuarterType.Q2, 5: QuarterType.Q2, 6: QuarterType.Q2,
        7: QuarterType.Q3, 8: QuarterType.Q3, 9: QuarterType.Q3,
        10: QuarterType.Q4, 11: QuarterType.Q4, 12: QuarterType.Q4,
    }[d.month]


# ============================================
# QUARTER MODEL
# ============================================
class Quarter(Base):
    __tablename__ = "quarter"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    quarter_type = Column(Enum(QuarterType, name="quartertype"), nullable=False)
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
    payments = relationship("Payment", back_populates="quarter")

    @property
    def number_of_waterpolo_users(self) -> int:
        return sum(1 for qu in (self.quarter_users or []) if qu.type_of_training == "waterpolo")

    @property
    def number_of_swimming_users(self) -> int:
        return sum(1 for qu in (self.quarter_users or []) if qu.type_of_training == "swimming")

    def __repr__(self):
        return f"<Quarter(id={self.id}, quarter_type='{self.quarter_type}', year={self.year})>"
