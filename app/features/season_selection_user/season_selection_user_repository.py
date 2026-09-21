# ============================================
# SEASON SELECTION USER REPOSITORY - Database Operations
# ============================================

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.season.season_model import Season
from app.features.season_selection_user.season_selection_user_model import SeasonSelectionUser
from app.features.sifarnici.selection.selection_model import Selection
from app.features.users.users_models import User


class SeasonSelectionUserRepository(CrudRepository[SeasonSelectionUser]):
    def __init__(self, db: Session):
        super().__init__(db, SeasonSelectionUser)

    def company_scope_clause(self, company_id: int):
        """No company_id column — a row belongs to its season's company."""
        return SeasonSelectionUser.season_id.in_(
            select(Season.id).where(Season.company_id == company_id)
        )

    def get_list_relations(self):
        return [
            lambda: selectinload(SeasonSelectionUser.season),
            lambda: selectinload(SeasonSelectionUser.selection),
            lambda: selectinload(SeasonSelectionUser.user),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(SeasonSelectionUser.season),
            lambda: selectinload(SeasonSelectionUser.selection),
            lambda: selectinload(SeasonSelectionUser.user),
        ]

    # ── Lookups used by create validation ───────────

    def get_season(self, season_id: int) -> Optional[Season]:
        return self.db.get(Season, season_id)

    def get_selection(self, selection_id: int) -> Optional[Selection]:
        return self.db.get(Selection, selection_id)

    def get_user(self, user_id: int) -> Optional[User]:
        return self.db.get(User, user_id)

    def exists(self, season_id: int, selection_id: int, user_id: int) -> bool:
        return (
            self.db.query(SeasonSelectionUser.id)
            .filter(
                SeasonSelectionUser.season_id == season_id,
                SeasonSelectionUser.selection_id == selection_id,
                SeasonSelectionUser.user_id == user_id,
            )
            .first()
            is not None
        )

    def delete(self, obj_id: int) -> bool:
        obj = self.db.get(SeasonSelectionUser, obj_id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
