# ============================================
# TRAINING REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.training.training_model import Training


class TrainingRepository(CrudRepository[Training]):
    def __init__(self, db: Session):
        super().__init__(db, Training)

    def get_list_relations(self):
        return [
            lambda: selectinload(Training.company),
            lambda: selectinload(Training.pool),
            lambda: selectinload(Training.training_type),
            lambda: selectinload(Training.training_users_list),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Training.company),
            lambda: selectinload(Training.pool),
            lambda: selectinload(Training.training_type),
            lambda: selectinload(Training.training_users_list),
        ]
