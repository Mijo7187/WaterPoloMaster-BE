# ============================================
# SEASON REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.season.season_model import Season


class SeasonRepository(CrudRepository[Season]):
    def __init__(self, db: Session):
        super().__init__(db, Season)

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Season.company),
        ]

    def clear_current_for_company(self, company_id: int, except_id: int = None) -> None:
        """Unset is_current on every other season of the company — only one may be current."""
        q = self.db.query(Season).filter(
            Season.company_id == company_id,
            Season.is_current.is_(True),
        )
        if except_id is not None:
            q = q.filter(Season.id != except_id)
        q.update({Season.is_current: False}, synchronize_session=False)
