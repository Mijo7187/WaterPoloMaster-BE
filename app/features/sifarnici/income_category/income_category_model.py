
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UUID
from sqlalchemy.sql import func

from app.core.db.base import Base


class IncomeCategory(Base):
    __tablename__ = "income_category"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    label = Column(String(255), nullable=False)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallet.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<IncomeCategory(id={self.id}, label={self.label})>"
