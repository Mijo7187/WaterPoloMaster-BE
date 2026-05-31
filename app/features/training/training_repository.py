# ============================================
# TRAINING REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.training.training_model import Training
from app.features.users.users_models import User


class TrainingRepository(CrudRepository[Training]):
    def __init__(self, db: Session):
        super().__init__(db, Training)

    def get_list_relations(self):
        return [
            lambda: selectinload(Training.company),
            lambda: selectinload(Training.users),
            lambda: selectinload(Training.pool),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Training.company),
            lambda: selectinload(Training.users),
            lambda: selectinload(Training.pool),
        ]

    def apply_create_relations(self, db_obj, data: dict) -> None:
        user_ids = data.pop("users_list", [])
        if user_ids:
            db_obj.users = self.db.query(User).filter(User.id.in_(user_ids)).all()

    def apply_update_relations(self, db_obj, data: dict) -> None:
        if "users_list" in data:
            user_ids = data.pop("users_list")
            db_obj.users = self.db.query(User).filter(User.id.in_(user_ids)).all()
