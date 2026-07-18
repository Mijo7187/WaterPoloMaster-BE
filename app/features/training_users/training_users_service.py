from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudCreateSchema
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import ConflictException, NotFoundException
from app.features.training_users.training_users_model import TrainingUsers
from app.features.training_users.training_users_repository import TrainingUsersRepository


class TrainingUsersService(CrudService[TrainingUsers]):
    def __init__(self, db: Session):
        super().__init__(db, TrainingUsersRepository(db))

    def create(self, data: CrudCreateSchema, **kwargs):
        existing = (
            self.db.query(TrainingUsers)
            .filter(
                TrainingUsers.training_id == data.training_id,
                TrainingUsers.user_id == data.user_id,
            )
            .first()
        )
        if existing:
            raise ConflictException("User is already registered for this training")
        return super().create(data, **kwargs)

    def delete(self, obj_id: int) -> None:
        obj = self.db.get(TrainingUsers, obj_id)
        if not obj:
            raise NotFoundException("Training user entry not found")
        self.db.delete(obj)
        self.db.commit()

    def get_users_not_in_training(self, training_id: int, company_id: int, page: int = 1, size: int = 20):
        return self.repository.get_users_not_in_training(training_id, company_id, page, size)
