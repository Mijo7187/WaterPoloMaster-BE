# ============================================
# QUARTER REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.quarter.quarter_model import Quarter


class QuarterRepository(CrudRepository[Quarter]):
    def __init__(self, db: Session):
        super().__init__(db, Quarter)

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
