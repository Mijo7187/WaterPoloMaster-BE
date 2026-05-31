import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(Base):
    __tablename__ = "payment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallet.id"), nullable=False)
    receiver_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallet.id"), nullable=False)
    payment_type_id = Column(Integer, ForeignKey("payment_type.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender_wallet = relationship(
        "Wallet", foreign_keys=[sender_wallet_id], back_populates="sent_payments"
    )
    receiver_wallet = relationship(
        "Wallet", foreign_keys=[receiver_wallet_id], back_populates="received_payments"
    )
    payment_type = relationship("PaymentType", back_populates="payments")

    def __repr__(self):
        return f"<Payment(id={self.id}, amount={self.amount}, status={self.status})>"
