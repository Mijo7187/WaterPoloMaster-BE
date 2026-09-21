# ============================================
# COMPANY MODEL - Database Table
# ============================================

import enum
from pydantic.v1 import validator
from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


# ============================================
# COMPANY TYPE ENUM
# ============================================
class CompanyType(str, enum.Enum):
    CLUB = "CLUB"
    POOL = "POOL"
    SUPPLIER = "SUPPLIER"
    ACADEMY = "ACADEMY"
    


class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, server_default="true")
    address = Column(String(500), nullable=True)
    city_id = Column(Integer, ForeignKey("city.id"), nullable=True)
    country_id = Column(Integer, ForeignKey("country.id"), nullable=True)
    phone_number = Column(String(50), nullable=True)
    email = Column(String(200), nullable=True)
    company_type = Column(String(20), default=CompanyType.CLUB.value, nullable=False, server_default=CompanyType.CLUB.value)

    # Adjacency list: a company belongs to at most one ACADEMY company.
    # NULL → not part of any academy.
    academy_id = Column(Integer, ForeignKey("company.id"), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    w_id = Column(UUID(as_uuid=True), ForeignKey("wallet.id"), nullable=True)
    wallet = relationship("Wallet", foreign_keys=[w_id], uselist=False)

    academy = relationship(
        "Company",
        remote_side=[id],
        foreign_keys=[academy_id],
        back_populates="academy_members",
    )
    academy_members = relationship(
        "Company",
        foreign_keys=[academy_id],
        back_populates="academy",
    )

    users = relationship("User", back_populates="company")
    city = relationship("City")
    country = relationship("Country")

    def __repr__(self):
        return f"<Company(id={self.id}, name='{self.name}')>"
