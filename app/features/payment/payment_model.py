import enum
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, UUID,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base
from app.features.wallet.wallet_model import WalletOwnerType


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentTypeCode(str, enum.Enum):
    USER_MEMBERSHIP_FEE = "user_membership_fee"   # U_C  - user pays membership dues to club
    USER_TOURNAMENT_FEE = "user_tournament_fee"   # U_C  - user pays tournament entry to club
    CLUB_TOURNAMENT_POOL = "club_tournament_pool" # C_C  - club pays pool for tournament hosting
    CLUB_SALARY_USER = "club_salary_user"         # C_U  - club pays salary to user
    CLUB_TRAINING_POOL = "club_training_pool"     # C_C  - club pays pool for training


class PayableType(str, enum.Enum):
    """What a payment is FOR. Deliberately open-ended — equipment orders,
    training camps and club-specific charges are expected to join this list,
    which is exactly why payable_id carries no DB foreign key."""

    CONTRACT_INSTALLMENT = "contract_installment"
    TOURNAMENT = "tournament"
    TRAINING = "training"
    


@dataclass(frozen=True)
class PaymentTypeSpec:
    """Static semantics of a payment type: display name, the wallet owner types
    it flows between, and which payable type (if any) it must point at."""

    name: str
    sender_type: WalletOwnerType
    receiver_type: WalletOwnerType
    required_context: Optional[PayableType]


# Single source of truth for payment types. `payable_type` says WHAT is paid;
# it does NOT say who pays whom — USER_TOURNAMENT_FEE and CLUB_TOURNAMENT_POOL
# both point at a tournament but flow in opposite directions. This registry is
# the authority on direction, and since payable_id carries no DB foreign key it
# is now also the integrity guard that replaces it (enforced in payment_service).
PAYMENT_TYPE_SPECS: dict[PaymentTypeCode, PaymentTypeSpec] = {
    PaymentTypeCode.USER_MEMBERSHIP_FEE: PaymentTypeSpec(
        "User Membership Fee", WalletOwnerType.USER, WalletOwnerType.COMPANY,
        PayableType.CONTRACT_INSTALLMENT,
    ),
    PaymentTypeCode.USER_TOURNAMENT_FEE: PaymentTypeSpec(
        "User Tournament Fee", WalletOwnerType.USER, WalletOwnerType.COMPANY,
        PayableType.TOURNAMENT,
    ),
    PaymentTypeCode.CLUB_TOURNAMENT_POOL: PaymentTypeSpec(
        "Club Tournament Pool", WalletOwnerType.COMPANY, WalletOwnerType.COMPANY,
        PayableType.TOURNAMENT,
    ),
    # Points at the STAFF contract_installment it pays, same as membership dues.
    PaymentTypeCode.CLUB_SALARY_USER: PaymentTypeSpec(
        "Club Salary User", WalletOwnerType.COMPANY, WalletOwnerType.USER,
        PayableType.CONTRACT_INSTALLMENT,
    ),
    PaymentTypeCode.CLUB_TRAINING_POOL: PaymentTypeSpec(
        "Club Training Pool", WalletOwnerType.COMPANY, WalletOwnerType.COMPANY,
        PayableType.TRAINING,
    ),
}


class Payment(Base):
    __tablename__ = "payment"
    __table_args__ = (
        Index("ix_payment_payable", "payable_type", "payable_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallet.id"), nullable=False)
    receiver_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallet.id"), nullable=False)
    payment_type = Column(Enum(PaymentTypeCode, name="paymenttypecode"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    description = Column(String(500), nullable=True)

    # Polymorphic payable reference. NO foreign key, by design — the set of
    # payable things grows (equipment, camps, club-specific charges) and a
    # typed FK column per kind does not scale. Integrity is guarded in
    # payment_service against PAYMENT_TYPE_SPECS + a live existence check.
    payable_type = Column(Enum(PayableType, name="payabletype"), nullable=True, index=True)
    payable_id = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender_wallet = relationship(
        "Wallet", foreign_keys=[sender_wallet_id], back_populates="sent_payments"
    )
    receiver_wallet = relationship(
        "Wallet", foreign_keys=[receiver_wallet_id], back_populates="received_payments"
    )
    # No `quarter`/`tournament`/`training` relationships any more — the payable
    # is resolved in batch by app/common/resolver/polymorphic_resolver.py.

    def __repr__(self):
        return f"<Payment(id={self.id}, amount={self.amount}, status={self.status})>"
