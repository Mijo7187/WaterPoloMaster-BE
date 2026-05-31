import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base
from app.features.wallet.wallet_model import WalletOwnerType


class PaymentTypeCode(str, enum.Enum):
    USER_QUARTERLY_FEE = "user_quarterly_fee"         # U_C  - user pays quarter to club
    USER_TOURNAMENT_FEE = "user_tournament_fee"       # U_C  - user pays tournament entry to club
    CLUB_TOURNAMENT_POOL = "club_tournament_pool"     # C_C  - club pays pool for tournament hosting
    CLUB_SALARY_USER = "club_salary_user"             # C_U  - club pays salary to user
    CLUB_TRAINING_POOL = "club_training_pool"         # C_C  - club pays pool for training

class PaymentType(Base):
    __tablename__ = "payment_type"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    code = Column(Enum(PaymentTypeCode), nullable=False)
    sender_type = Column(Enum(WalletOwnerType), nullable=False)
    receiver_type = Column(Enum(WalletOwnerType), nullable=False)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    payments = relationship("Payment", back_populates="payment_type")

    def __repr__(self):
        return f"<PaymentType(id={self.id}, code={self.code}, name={self.name})>"
