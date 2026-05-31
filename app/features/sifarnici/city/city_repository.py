# ============================================
# CITY REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.sifarnici.city.city_model import City


class CityRepository(CrudRepository[City]):
    def __init__(self, db: Session):
        super().__init__(db, City)

    def get_list_relations(self):
        return [
            lambda: selectinload(City.country),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(City.country),
        ]
