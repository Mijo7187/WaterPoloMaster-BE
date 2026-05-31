# ============================================
# COUNTRY REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.sifarnici.country.country_model import Country


class CountryRepository(CrudRepository[Country]):
    def __init__(self, db: Session):
        super().__init__(db, Country)
