# ============================================
# TRAINING TYPE REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.sifarnici.training_type.training_type_model import TrainingType


class TrainingTypeRepository(CrudRepository[TrainingType]):
    def __init__(self, db: Session):
        super().__init__(db, TrainingType)
