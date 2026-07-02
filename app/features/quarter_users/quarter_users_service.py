from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudCreateSchema
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import ConflictException, NotFoundException
from app.features.quarter_users.quarter_users_model import QuarterUsers
from app.features.quarter_users.quarter_users_repository import QuarterUsersRepository


class QuarterUsersService(CrudService[QuarterUsers]):
    def __init__(self, db: Session):
        super().__init__(db, QuarterUsersRepository(db))

    def create(self, data: CrudCreateSchema, **kwargs):
        existing = (
            self.db.query(QuarterUsers)
            .filter(
                QuarterUsers.quarter_id == data.quarter_id,
                QuarterUsers.user_id == data.user_id,
            )
            .first()
        )
        if existing:
            raise ConflictException("User is already registered for this quarter")
        if hasattr(data.type_of_training, "value"):
            data.type_of_training = data.type_of_training.value
        return super().create(data, **kwargs)

    def delete(self, obj_id: int) -> None:
        obj = self.db.get(QuarterUsers, obj_id)
        if not obj:
            raise NotFoundException("Quarter user entry not found")
        self.db.delete(obj)
        self.db.commit()

    def get_users_not_in_quarter(self, quarter_id: int, company_id: int, page: int = 1, size: int = 20):
        return self.repository.get_users_not_in_quarter(quarter_id, company_id, page, size)
