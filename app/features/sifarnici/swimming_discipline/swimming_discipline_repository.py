# ============================================
# SWIMMING DISCIPLINE REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.sifarnici.swimming_discipline.swimming_discipline_model import SwimmingDiscipline


class SwimmingDisciplineRepository(CrudRepository[SwimmingDiscipline]):
    def __init__(self, db: Session):
        super().__init__(db, SwimmingDiscipline)
