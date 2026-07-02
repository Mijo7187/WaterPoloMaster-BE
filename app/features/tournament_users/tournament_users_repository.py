from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.tournament_users.tournament_users_model import TournamentUsers
from app.features.users.users_models import User


class TournamentUsersRepository(CrudRepository[TournamentUsers]):
    def __init__(self, db: Session):
        super().__init__(db, TournamentUsers)

    def get_list_relations(self):
        return [
            lambda: selectinload(TournamentUsers.user),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(TournamentUsers.user),
        ]

    def get_users_not_in_tournament(self, tournament_id: int, company_id: int, page: int = 1, size: int = 20):
        subq = (
            self.db.query(TournamentUsers.user_id)
            .filter(TournamentUsers.tournament_id == tournament_id)
            .subquery()
        )
        q = self.db.query(User).filter(
            ~User.id.in_(subq),
            User.company_id == company_id,
        )
        total = q.count()
        items = q.offset((page - 1) * size).limit(size).all()
        return items, total
