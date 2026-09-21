# ============================================
# MEMBERSHIP MODEL - Database Tables
# ============================================
# A club's price catalog: one row per plan it sells.
#
# This replaces the old season -> selection -> selection_offering ->
# offering_price chain. Offers are no longer made per season or per
# selection, so a membership belongs to nothing but its company.
#
# `months_count` is the term length in months. It replaces the old
# BillingFrequency enum (MONTHLY/QUARTERLY/YEARLY), so a club can sell a
# 4- or 10-month plan without a schema change. `price_month` is the price
# for ONE month — the term total is price_month * months_count, split into
# `installments_count` equal installments.
# ============================================

import enum

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class Program(str, enum.Enum):
    SWIMMING = "swimming"
    WATERPOLO = "waterpolo"


def divides_term_evenly(months_count: int, installments_count: int) -> bool:
    """Whether the term splits into whole-month installments.

    A 3-month term takes 1 or 3 installments; 2 would give 1.5 months each.
    A 12-month term takes 1, 2, 3, 4, 6 or 12.
    """
    if not months_count or not installments_count or installments_count < 1:
        return False
    return months_count % installments_count == 0


class Membership(Base):
    __tablename__ = "membership"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "name", "program",
            name="uq_membership_company_name_program",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("company.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    program = Column(Enum(Program, name="program"), nullable=False)

    # The term length in months — replaces the old BillingFrequency enum.
    months_count = Column(Integer, nullable=False, default=1)
    # Price for ONE month. The term total is price_month * months_count.
    price_month = Column(Numeric(10, 2), nullable=False)
    installments_count = Column(Integer, nullable=False, default=1)

    # Retires a plan without deleting it: it drops out of the catalog but
    # anything already referencing it stays readable.
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company")

    def __repr__(self):
        return (
            f"<Membership(id={self.id}, name='{self.name}', "
            f"program='{self.program}', months_count={self.months_count})>"
        )
