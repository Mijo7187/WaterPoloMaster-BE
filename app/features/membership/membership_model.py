# ============================================
# MEMBERSHIP MODEL - Database Tables
# ============================================
# A club's price catalog: one row per plan it sells, per selection.
#
# `billing_type` decides how a contract signed off the plan is billed:
#   * MONTHLY — open-ended. `price` is the MONTHLY amount and the recurring
#     job adds one installment per month for as long as the contract is
#     ACTIVE. There is no term and no end date; you cancel, you don't re-sign.
#   * TERM — a fixed block (masters-style quarterly). `price` is the price of
#     the WHOLE block and `term_months` its length. One installment is written
#     at activation and the recurring job never touches it. The next block is
#     a new contract.
#
# `selection_id` is what makes "debt per group" derivable without storing a
# group on the contract. A group is (selection, season), so the debt of one
# group is:
#     sum(installment.amount - paid) for installments where
#         installment.contract.membership.selection = <selection>
#         AND installment period falls within <season>.[start_date, end_date]
#         AND NOT waived AND unpaid
#         [AND contract.company_id = <club>  -- omit for the whole academy]
# One contract -> one membership -> one selection -> one group per season, so
# nothing is double-counted and no `group_id` column is needed anywhere.
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


class BillingType(str, enum.Enum):
    MONTHLY = "monthly"  # open-ended, one installment per ACTIVE month
    TERM = "term"        # one fixed block, billed once


class Membership(Base):
    __tablename__ = "membership"
    __table_args__ = (
        # A club sells at most one plan per (selection, program, billing type).
        # `name` is a free-text label and is deliberately NOT part of the key.
        UniqueConstraint(
            "company_id", "selection_id", "program", "billing_type",
            name="uq_membership_company_selection_program_type",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("company.id"), nullable=False, index=True)
    selection_id = Column(
        Integer, ForeignKey("selection.id"), nullable=False, index=True
    )
    program = Column(Enum(Program, name="program"), nullable=False)

    billing_type = Column(Enum(BillingType, name="billingtype"), nullable=False)

    # MONTHLY: the monthly amount. TERM: the price of the whole block.
    price = Column(Numeric(10, 2), nullable=False)
    # TERM only — the block length in months. NULL for MONTHLY.
    term_months = Column(Integer, nullable=True)

    # Optional display label ("Masters Q1", "U15 waterpolo").
    name = Column(String(255), nullable=True)

    # Retires a plan without deleting it: it drops out of the catalog but
    # anything already referencing it stays readable.
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    selection = relationship("Selection")

    def __repr__(self):
        return (
            f"<Membership(id={self.id}, selection_id={self.selection_id}, "
            f"program='{self.program}', billing_type='{self.billing_type}')>"
        )
