from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.training_users_list.training_users_list_model import TrainingUsersList
from app.features.users.users_models import User


class TrainingUsersListRepository(CrudRepository[TrainingUsersList]):
    def __init__(self, db: Session):
        super().__init__(db, TrainingUsersList)

    def get_list_relations(self):
        return [
            lambda: selectinload(TrainingUsersList.user),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(TrainingUsersList.user),
        ]

    def get_users_not_in_training(self, training_id: int, company_id: int, page: int = 1, size: int = 20):
        subq = (
            self.db.query(TrainingUsersList.user_id)
            .filter(TrainingUsersList.training_id == training_id)
            .subquery()
        )
        q = self.db.query(User).filter(
            ~User.id.in_(subq),
            User.company_id == company_id,
        )
        total = q.count()
        items = q.offset((page - 1) * size).limit(size).all()
        return items, total
