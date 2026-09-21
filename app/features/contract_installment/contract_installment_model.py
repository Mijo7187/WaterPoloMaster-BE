# ============================================
# CONTRACT INSTALLMENT MODEL - Database Tables
# ============================================
# Per-period obligations generated from a contract when it is activated.
# Real rows (not computed on the fly) so waivers, mid-term price changes and
# "who owes month X" all work.
#
# `waived` is the ONLY stored payment-state. paid/pending/partial is computed
# from the payments that point at the installment, never stored.
#
# MEMBERSHIP generates dues user→club, STAFF generates dues club→user — same
# mechanism, direction taken from the contract (CONTRACT_TYPE_SPECS).
# ============================================

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class ContractInstallment(Base):
    __tablename__ = "contract_installment"
    __table_args__ = (
        # Makes installment generation idempotent at the DB level.
        UniqueConstraint(
            "contract_id", "period_start", name="uq_installment_contract_period"
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    contract_id = Column(
        Integer, ForeignKey("contract.id"), nullable=False, index=True
    )
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    waived = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    contract = relationship("Contract", back_populates="installments")

    def __repr__(self):
        return (
            f"<ContractInstallment(id={self.id}, contract_id={self.contract_id}, "
            f"period_start={self.period_start}, amount={self.amount})>"
        )
