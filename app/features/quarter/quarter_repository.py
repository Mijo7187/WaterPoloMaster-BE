# ============================================
# QUARTER REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.quarter.quarter_model import Quarter
from app.features.quarter_users.quarter_users_model import QuarterUsers


class QuarterRepository(CrudRepository[Quarter]):
    def __init__(self, db: Session):
        super().__init__(db, Quarter)

    def _apply_filter(self, q, key, value):
        # `user_id` is a virtual filter (no such column on quarter): match
        # quarters the user belongs to via the quarter_users join table.
        # Everything else falls through to the generic per-field filtering.
        if key == "user_id":
            return q.filter(
                Quarter.quarter_users.any(QuarterUsers.user_id == value)
            )
        return super()._apply_filter(q, key, value)

    def get_list_relations(self):
        return [
            lambda: selectinload(Quarter.quarter_users),
            lambda: selectinload(Quarter.company),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Quarter.quarter_users),
            lambda: selectinload(Quarter.company),
        ]
