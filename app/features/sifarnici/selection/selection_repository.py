# ============================================
# SELECTION REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.sifarnici.selection.selection_model import Selection


class SelectionRepository(CrudRepository[Selection]):
    def __init__(self, db: Session):
        super().__init__(db, Selection)
