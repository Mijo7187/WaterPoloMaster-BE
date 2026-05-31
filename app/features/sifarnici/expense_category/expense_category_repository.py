from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.sifarnici.expense_category.expense_category_model import ExpenseCategory


class ExpenseCategoryRepository(CrudRepository[ExpenseCategory]):
    def __init__(self, db: Session):
        super().__init__(db, ExpenseCategory)
