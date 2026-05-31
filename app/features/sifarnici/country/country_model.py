# ============================================
# COUNTRY MODEL - Database Table
# ============================================

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.db.base import Base


class Country(Base):
    __tablename__ = "country"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    cities = relationship("City", back_populates="country")

    def __repr__(self):
        return f"<Country(id={self.id}, name='{self.name}')>"
