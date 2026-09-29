# ============================================
# GROUP MODEL - Database Table
# ============================================
# A group is a selection (U15, U17, Masters, ...) in one season — the squad a
# club actually trains and bills. The pair IS the identity, so only
# (season_id, selection_id) is unique; who is in it lives in `group_user`.
#
# This is the unit "debt per group" is reported over. Nothing stores a group
# on a contract: a contract points at a membership, a membership at a
# selection, and the installment's period places it in a season. One contract
# -> one selection -> one group per season, so nothing is double-counted.
#
# There is no company_id column: the company is the season's company, and the
# service rejects a row whose season and selection disagree on the academy
# they belong to.
#
# NOTE: `group` is a reserved SQL keyword. SQLAlchemy quotes identifiers
# automatically, but any raw SQL (e.g. in a migration) must write "group".
# ============================================

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class Group(Base):
    __tablename__ = "group"
    __table_args__ = (
        UniqueConstraint("season_id", "selection_id", name="uq_group_season_selection"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    season_id = Column(
        Integer, ForeignKey("season.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selection_id = Column(
        Integer, ForeignKey("selection.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    season = relationship("Season")
    selection = relationship("Selection")
    members = relationship(
        "GroupUser", back_populates="group", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<Group(id={self.id}, season_id={self.season_id}, "
            f"selection_id={self.selection_id})>"
        )
