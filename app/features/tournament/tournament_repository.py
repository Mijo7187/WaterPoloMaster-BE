# ============================================
# TOURNAMENT REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.tournament.tournament_model import Tournament


class TournamentRepository(CrudRepository[Tournament]):
    def __init__(self, db: Session):
        super().__init__(db, Tournament)

    def get_list_relations(self):
        return [
            lambda: selectinload(Tournament.tournament_users),
            lambda: selectinload(Tournament.company),
            lambda: selectinload(Tournament.pool),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Tournament.tournament_users),
            lambda: selectinload(Tournament.company),
            lambda: selectinload(Tournament.pool),
        ]
