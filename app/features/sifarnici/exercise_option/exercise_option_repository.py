# ============================================
# EXERCISE OPTION REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.sifarnici.exercise_option.exercise_option_model import ExerciseOption


class ExerciseOptionRepository(CrudRepository[ExerciseOption]):
    def __init__(self, db: Session):
        super().__init__(db, ExerciseOption)
