# ============================================
# TRAINING TYPE SERVICE - Business Logic
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.features.sifarnici.training_type.training_type_model import TrainingType
from app.features.sifarnici.training_type.training_type_repository import TrainingTypeRepository


class TrainingTypeService(CrudService[TrainingType]):
    def __init__(self, db: Session):
        super().__init__(db, TrainingTypeRepository(db))
