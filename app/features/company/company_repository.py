# ============================================
# COMPANY REPOSITORY - Database Operations
# ============================================

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.company.company_model import Company, CompanyType


class CompanyRepository(CrudRepository[Company]):
    def __init__(self, db: Session):
        super().__init__(db, Company)

    def company_scope_clause(self, company_id: int):
        """
        Company has no company_id — its own id is the scope key.

        Pools and suppliers stay visible to everyone: a training or tournament
        picks a pool_id belonging to another company, so hiding them would break
        the picker. Other CLUBs are hidden.
        """
        return or_(
            Company.id == company_id,
            Company.company_type.in_((CompanyType.POOL.value, CompanyType.SUPPLIER.value)),
        )

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
            lambda: selectinload(Company.academy),
        ]
