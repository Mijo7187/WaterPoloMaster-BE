from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class TournamentUsers(Base):
    __tablename__ = "tournament_users"
    __table_args__ = (UniqueConstraint("tournament_id", "user_id"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tournament_id = Column(Integer, ForeignKey("tournament.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tournament = relationship("Tournament", back_populates="tournament_users")
    user = relationship("User")

    def __repr__(self):
        return f"<TournamentUsers(tournament_id={self.tournament_id}, user_id={self.user_id})>"
