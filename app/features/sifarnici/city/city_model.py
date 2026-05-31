# ============================================
# CITY MODEL - Database Table
# ============================================

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.db.base import Base


class City(Base):
    __tablename__ = "city"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    country_id = Column(Integer, ForeignKey("country.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    country = relationship("Country", back_populates="cities")

    def __repr__(self):
        return f"<City(id={self.id}, name='{self.name}')>"
