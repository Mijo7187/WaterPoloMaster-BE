# ============================================
# COMPANY REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.company.company_model import Company


class CompanyRepository(CrudRepository[Company]):
    def __init__(self, db: Session):
        super().__init__(db, Company)

    def get_list_relations(self):
        return [
            lambda: selectinload(Company.city),
            lambda: selectinload(Company.country),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Company.city),
            lambda: selectinload(Company.country),
            lambda: selectinload(Company.wallet),
        ]
