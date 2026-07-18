# ============================================
# EXERCISE OPTION SERVICE - Business Logic
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.features.sifarnici.exercise_option.exercise_option_model import ExerciseOption
from app.features.sifarnici.exercise_option.exercise_option_repository import ExerciseOptionRepository


class ExerciseOptionService(CrudService[ExerciseOption]):
    def __init__(self, db: Session):
        super().__init__(db, ExerciseOptionRepository(db))
