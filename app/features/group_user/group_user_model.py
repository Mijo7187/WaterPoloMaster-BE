# ============================================
# GROUP USER MODEL - Database Table
# ============================================
# Who is in a group. The group already fixes the season and the selection, so
# a row here is just "this player trains with this squad".
#
# A user may hold several groups in one season (a strong player can train with
# U15 and U17) — those are separate rows, and only (group, user) is unique.
#
# MEMBERSHIP contracts write a row here automatically, through the
# membership's selection and the academy's current season. Extra groups for a
# player are hand-added rows, unrelated to any contract.
#
# Rows are never edited — moving a player is delete + create.
# ============================================

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class GroupUser(Base):
    __tablename__ = "group_user"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_user"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    group_id = Column(
        Integer, ForeignKey("group.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group = relationship("Group", back_populates="members")
    user = relationship("User")

    def __repr__(self):
        return f"<GroupUser(group_id={self.group_id}, user_id={self.user_id})>"
