# ============================================
# TOURNAMENT REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.tournament.tournament_model import Tournament
from app.features.tournament_users.tournament_users_model import TournamentUsers


class TournamentRepository(CrudRepository[Tournament]):
    def __init__(self, db: Session):
        super().__init__(db, Tournament)

    def _apply_filter(self, q, key, value):
        # `user_id` is a virtual filter (no such column on tournament): match
        # tournaments the user belongs to via the tournament_users join table.
        # Everything else falls through to the generic per-field filtering.
        if key == "user_id":
            return q.filter(
                Tournament.tournament_users.any(TournamentUsers.user_id == value)
            )
        return super()._apply_filter(q, key, value)

    def get_list_relations(self):
        return [
            lambda: selectinload(Tournament.tournament_users),
            lambda: selectinload(Tournament.company),
            lambda: selectinload(Tournament.pool),
            lambda: selectinload(Tournament.quarter),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Tournament.tournament_users),
            lambda: selectinload(Tournament.company),
            lambda: selectinload(Tournament.pool),
            lambda: selectinload(Tournament.quarter),
        ]
