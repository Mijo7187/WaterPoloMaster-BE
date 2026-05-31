import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, Integer, UniqueConstraint, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class WalletOwnerType(str, enum.Enum):
    USER = "USER"
    COMPANY = "COMPANY"


class Wallet(Base):
    __tablename__ = "wallet"
    __table_args__ = (
        UniqueConstraint("owner_id", "owner_type", name="uq_wallet_owner"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Polymorphic — references users.id or company.id (both Integer PKs)
    owner_id = Column(Integer, nullable=False)
    owner_type = Column(Enum(WalletOwnerType), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sent_payments = relationship(
        "Payment", foreign_keys="Payment.sender_wallet_id", back_populates="sender_wallet"
    )
    received_payments = relationship(
        "Payment", foreign_keys="Payment.receiver_wallet_id", back_populates="receiver_wallet"
    )

    def __repr__(self):
        return f"<Wallet(id={self.id}, owner_type={self.owner_type}, owner_id={self.owner_id})>"
