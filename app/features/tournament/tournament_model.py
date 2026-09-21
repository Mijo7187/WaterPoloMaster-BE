# ============================================
# TOURNAMENT MODEL - Database Tables
# ============================================

from sqlalchemy import (
    Column, Integer, Numeric, DateTime, Date, String, ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base
from app.utils.dateUtils import quarter_type_for_date


# ============================================
# TOURNAMENT MODEL
# ============================================
class Tournament(Base):
    __tablename__ = "tournament"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    pool_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    description = Column(String(255), nullable=True)
    season_id = Column(Integer, ForeignKey("season.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    pool = relationship("Company", foreign_keys=[pool_id])
    season = relationship("Season")
    tournament_users = relationship("TournamentUsers", back_populates="tournament")

    @property
    def number_of_users(self) -> int:
        return len(self.tournament_users or [])

    @property
    def quarter_type(self):
        """Calendar quarter label, derived from the date. There is no quarter
        table any more — the billing period is `season`."""
        return quarter_type_for_date(self.from_date) if self.from_date else None

    def __repr__(self):
        return f"<Tournament(id={self.id}, from_date='{self.from_date}', to_date='{self.to_date}')>"
