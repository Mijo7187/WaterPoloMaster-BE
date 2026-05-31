from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.features.sifarnici.income_category.income_category_model import IncomeCategory
from app.features.sifarnici.income_category.income_category_repository import IncomeCategoryRepository


class IncomeCategoryService(CrudService[IncomeCategory]):
    def __init__(self, db: Session):
        super().__init__(db, IncomeCategoryRepository(db))
