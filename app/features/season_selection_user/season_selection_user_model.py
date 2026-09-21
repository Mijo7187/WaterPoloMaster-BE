# ============================================
# SEASON SELECTION USER MODEL - Database Table
# ============================================
# Which selection (U15, U17, Masters, ...) a user is in, per season.
#
# A user may hold several selections in one season (a strong player can
# train with U15 and U17), so only the exact (season, selection, user)
# triple is unique.
#
# There is no company_id column: the company is the season's company, and
# the service rejects a row whose season, selection and user disagree on it.
# Rows are never edited — moving a player is delete + create.
# ============================================

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class SeasonSelectionUser(Base):
    __tablename__ = "season_selection_user"
    __table_args__ = (
        UniqueConstraint(
            "season_id", "selection_id", "user_id", name="uq_season_selection_user"
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    season_id = Column(
        Integer, ForeignKey("season.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selection_id = Column(
        Integer, ForeignKey("selection.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    season = relationship("Season")
    selection = relationship("Selection")
    user = relationship("User")

    def __repr__(self):
        return (
            f"<SeasonSelectionUser(season_id={self.season_id}, "
            f"selection_id={self.selection_id}, user_id={self.user_id})>"
        )
