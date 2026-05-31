from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.sifarnici.income_category.income_category_model import IncomeCategory


class IncomeCategoryRepository(CrudRepository[IncomeCategory]):
    def __init__(self, db: Session):
        super().__init__(db, IncomeCategory)
