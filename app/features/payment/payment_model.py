import enum
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, UUID
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
    USER_QUARTERLY_FEE = "user_quarterly_fee"     # U_C  - user pays quarter to club
    USER_TOURNAMENT_FEE = "user_tournament_fee"   # U_C  - user pays tournament entry to club
    CLUB_TOURNAMENT_POOL = "club_tournament_pool" # C_C  - club pays pool for tournament hosting
    CLUB_SALARY_USER = "club_salary_user"         # C_U  - club pays salary to user
    CLUB_TRAINING_POOL = "club_training_pool"     # C_C  - club pays pool for training


@dataclass(frozen=True)
class PaymentTypeSpec:
    """Static semantics of a payment type: display name, the wallet owner types
    it flows between, and which business-context id (if any) it requires."""

    name: str
    sender_type: WalletOwnerType
    receiver_type: WalletOwnerType
    required_context: Optional[str]  # "quarter_id" | "tournament_id" | "training_id" | None


# Single source of truth for payment types. Replaces the former `payment_type`
# reference table (a static seeded mirror of this enum) and the context dict that
# used to live in payment_service. Adding a type is a code change by design — each
# type is hardwired to specific sender/receiver semantics and a real context FK.
PAYMENT_TYPE_SPECS: dict[PaymentTypeCode, PaymentTypeSpec] = {
    PaymentTypeCode.USER_QUARTERLY_FEE: PaymentTypeSpec(
        "User Quarterly Fee", WalletOwnerType.USER, WalletOwnerType.COMPANY, "quarter_id"
    ),
    PaymentTypeCode.USER_TOURNAMENT_FEE: PaymentTypeSpec(
        "User Tournament Fee", WalletOwnerType.USER, WalletOwnerType.COMPANY, "tournament_id"
    ),
    PaymentTypeCode.CLUB_TOURNAMENT_POOL: PaymentTypeSpec(
        "Club Tournament Pool", WalletOwnerType.COMPANY, WalletOwnerType.COMPANY, "tournament_id"
    ),
    PaymentTypeCode.CLUB_SALARY_USER: PaymentTypeSpec(
        "Club Salary User", WalletOwnerType.COMPANY, WalletOwnerType.USER, None
    ),
    PaymentTypeCode.CLUB_TRAINING_POOL: PaymentTypeSpec(
        "Club Training Pool", WalletOwnerType.COMPANY, WalletOwnerType.COMPANY, "training_id"
    ),
}


class Payment(Base):
    __tablename__ = "payment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallet.id"), nullable=False)
    receiver_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallet.id"), nullable=False)
    payment_type = Column(Enum(PaymentTypeCode, name="paymenttypecode"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    description = Column(String(500), nullable=True)
    quarter_id = Column(Integer, ForeignKey("quarter.id"), nullable=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournament.id"), nullable=True, index=True)
    training_id = Column(Integer, ForeignKey("training.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender_wallet = relationship(
        "Wallet", foreign_keys=[sender_wallet_id], back_populates="sent_payments"
    )
    receiver_wallet = relationship(
        "Wallet", foreign_keys=[receiver_wallet_id], back_populates="received_payments"
    )
    quarter = relationship("Quarter", back_populates="payments")
    tournament = relationship("Tournament", back_populates="payments")
    training = relationship("Training", back_populates="payments")

    def __repr__(self):
        return f"<Payment(id={self.id}, amount={self.amount}, status={self.status})>"
