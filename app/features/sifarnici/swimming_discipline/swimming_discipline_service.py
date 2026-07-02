# ============================================
# SWIMMING DISCIPLINE SERVICE - Business Logic
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.features.sifarnici.swimming_discipline.swimming_discipline_model import SwimmingDiscipline
from app.features.sifarnici.swimming_discipline.swimming_discipline_repository import SwimmingDisciplineRepository


class SwimmingDisciplineService(CrudService[SwimmingDiscipline]):
    def __init__(self, db: Session):
        super().__init__(db, SwimmingDisciplineRepository(db))
