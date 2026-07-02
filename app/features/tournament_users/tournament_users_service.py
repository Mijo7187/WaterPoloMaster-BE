from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudCreateSchema
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import ConflictException, NotFoundException
from app.features.tournament_users.tournament_users_model import TournamentUsers
from app.features.tournament_users.tournament_users_repository import TournamentUsersRepository


class TournamentUsersService(CrudService[TournamentUsers]):
    def __init__(self, db: Session):
        super().__init__(db, TournamentUsersRepository(db))

    def create(self, data: CrudCreateSchema, **kwargs):
        existing = (
            self.db.query(TournamentUsers)
            .filter(
                TournamentUsers.tournament_id == data.tournament_id,
                TournamentUsers.user_id == data.user_id,
            )
            .first()
        )
        if existing:
            raise ConflictException("User is already registered for this tournament")
        return super().create(data, **kwargs)

    def delete(self, obj_id: int) -> None:
        obj = self.db.get(TournamentUsers, obj_id)
        if not obj:
            raise NotFoundException("Tournament user entry not found")
        self.db.delete(obj)
        self.db.commit()

    def get_users_not_in_tournament(self, tournament_id: int, company_id: int, page: int = 1, size: int = 20):
        return self.repository.get_users_not_in_tournament(tournament_id, company_id, page, size)
