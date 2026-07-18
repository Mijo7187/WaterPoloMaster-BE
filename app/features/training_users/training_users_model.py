from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class TrainingUsers(Base):
    __tablename__ = "training_users"
    __table_args__ = (UniqueConstraint("training_id", "user_id"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    training_id = Column(Integer, ForeignKey("training.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    training = relationship("Training", back_populates="training_users")
    user = relationship("User")

    def __repr__(self):
        return f"<TrainingUsers(training_id={self.training_id}, user_id={self.user_id})>"
