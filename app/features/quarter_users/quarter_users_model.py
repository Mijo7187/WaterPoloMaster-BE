import enum

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


# ============================================
# TYPE OF TRAINING ENUM
# ============================================
class TypeOfTraining(str, enum.Enum):
    WATERPOLO = "waterpolo"
    SWIMMING = "swimming"


class QuarterUsers(Base):
    __tablename__ = "quarter_users"
    __table_args__ = (UniqueConstraint("quarter_id", "user_id"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    quarter_id = Column(Integer, ForeignKey("quarter.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type_of_training = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    quarter = relationship("Quarter", back_populates="quarter_users")
    user = relationship("User")

    def __repr__(self):
        return f"<QuarterUsers(quarter_id={self.quarter_id}, user_id={self.user_id})>"
