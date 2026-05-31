# ============================================
# CITY SERVICE - Business Logic
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.features.sifarnici.city.city_model import City
from app.features.sifarnici.city.city_repository import CityRepository


class CityService(CrudService[City]):
    def __init__(self, db: Session):
        super().__init__(db, CityRepository(db))
