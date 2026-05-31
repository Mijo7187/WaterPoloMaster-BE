from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.features.sifarnici.expense_category.expense_category_model import ExpenseCategory
from app.features.sifarnici.expense_category.expense_category_repository import ExpenseCategoryRepository


class ExpenseCategoryService(CrudService[ExpenseCategory]):
    def __init__(self, db: Session):
        super().__init__(db, ExpenseCategoryRepository(db))
