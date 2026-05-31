# ============================================
# COUNTRY SERVICE - Business Logic
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.features.sifarnici.country.country_model import Country
from app.features.sifarnici.country.country_repository import CountryRepository


class CountryService(CrudService[Country]):
    def __init__(self, db: Session):
        super().__init__(db, CountryRepository(db))
