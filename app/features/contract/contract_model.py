# ============================================
# CONTRACT MODEL - Database Tables
# ============================================
# The signed agreement, ALWAYS between the club and one user.
#
# Design notes (these are load-bearing — see CLAUDE.md / the billing rewrite plan):
#   * A player's category for a season is a consequence of their contract.
#     There is deliberately NO category/selection/team column on `user`.
#   * `amount` and the installment schedule are agreed at signing and stored
#     here. The contract is self-contained: it does not read a catalog price,
#     so changing a `membership` later cannot touch it.
#   * `membership_id` is optional PROVENANCE — which catalog plan this contract
#     was signed off. On create it fills in the amount / installments_list the
#     caller omitted; after that it is inert, so editing or retiring the plan
#     never moves an existing contract. A bespoke contract (negotiated price,
#     no plan) simply leaves it NULL.
#   * A MEMBERSHIP contract's schedule is the `installments_list` sent at
#     create — one contract_installment row per entry. Its `end_date` is not
#     used for billing — you re-sign for the next term. STAFF is the opposite:
#     the monthly salary job adds one calendar-month installment of `amount`
#     (plus its PENDING payment) on the 1st of every month it is ACTIVE.
#   * Direction (who pays whom) is DERIVED from contract_type via
#     CONTRACT_TYPE_SPECS below — there is no stored direction flag, exactly
#     like PAYMENT_TYPE_SPECS in payment_model.
#   * A scholarship needs no special type or flag: it is a MEMBERSHIP contract
#     for which no installments are generated → no dues → nothing billed.
# ============================================

import enum
from dataclasses import dataclass

from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base
from app.features.payment.payment_model import PaymentTypeCode
from app.features.wallet.wallet_model import WalletOwnerType


class ContractType(str, enum.Enum):
    MEMBERSHIP = "membership"  # user pays club
    STAFF = "staff"            # club pays user


class ContractStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ENDED = "ended"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ContractTypeSpec:
    """Static semantics of a contract type: which payment type its installments
    become, and the wallet owner types money flows between. Mirrors
    PAYMENT_TYPE_SPECS — direction is derived from the type, never stored."""

    payment_type: PaymentTypeCode
    sender_type: WalletOwnerType
    receiver_type: WalletOwnerType


CONTRACT_TYPE_SPECS: dict[ContractType, ContractTypeSpec] = {
    ContractType.MEMBERSHIP: ContractTypeSpec(
        PaymentTypeCode.USER_MEMBERSHIP_FEE,
        WalletOwnerType.USER,
        WalletOwnerType.COMPANY,
    ),
    ContractType.STAFF: ContractTypeSpec(
        PaymentTypeCode.CLUB_SALARY_USER,
        WalletOwnerType.COMPANY,
        WalletOwnerType.USER,
    ),
}


class Contract(Base):
    __tablename__ = "contract"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("company.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    contract_type = Column(Enum(ContractType, name="contracttype"), nullable=False)

    # The catalog plan this contract was signed off, when there was one.
    # MEMBERSHIP only — a STAFF salary is never sold from the catalog.
    membership_id = Column(
        Integer, ForeignKey("membership.id"), nullable=True, index=True
    )

    # Agreed at signing. For MEMBERSHIP this is the TOTAL for the whole term —
    # the installments always sum back to it. For STAFF it is the monthly
    # salary.
    amount = Column(Numeric(10, 2), nullable=False)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # null = open-ended / indefinite
    status = Column(
        Enum(ContractStatus, name="contractstatus"),
        nullable=False,
        default=ContractStatus.DRAFT,
    )
    signed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    user = relationship("User")
    membership = relationship("Membership")
    installments = relationship(
        "ContractInstallment",
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="ContractInstallment.period_start",
    )

    @property
    def spec(self) -> ContractTypeSpec:
        return CONTRACT_TYPE_SPECS[ContractType(self.contract_type)]

    def __repr__(self):
        return (
            f"<Contract(id={self.id}, user_id={self.user_id}, "
            f"type='{self.contract_type}', status='{self.status}')>"
        )
