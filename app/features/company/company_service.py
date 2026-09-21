from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.features.company.company_model import Company, CompanyType
from app.features.company.company_repository import CompanyRepository


class CompanyService(CrudService[Company]):
    def __init__(self, db: Session):
        super().__init__(db, CompanyRepository(db))

    def enforce_company_scope(self, obj_id: int, current_user: Optional[Any]) -> None:
        """
        Writes ignore the read carve-out: seeing a pool or supplier does not
        mean you may edit it. Only your own company is writable.
        """
        company_id = self.company_scope_for(current_user)
        if company_id is not None and obj_id != company_id:
            raise ForbiddenException("You can only manage records in your own company.")

    def create(self, schema: BaseModel, current_user: Optional[Any] = None) -> Company:
        from app.features.wallet.wallet_model import Wallet, WalletOwnerType

        data = schema.model_dump()
        company = Company(**data)
        self.db.add(company)
        self.db.flush()

        wallet = Wallet(owner_id=company.id, owner_type=WalletOwnerType.COMPANY, name=company.name)
        self.db.add(wallet)
        self.db.flush()            # populate wallet.id before linking
        company.w_id = wallet.id   # the missing link
        self.db.commit()
        self.db.refresh(company)
        return company

    # ── Academy membership ──────────────────────────
    # A company belongs to at most one academy, held in Company.academy_id.
    # Membership is managed only through the dedicated /academy endpoints,
    # never through company create/update.

    def _get_academy(self, academy_id: int) -> Company:
        academy = self.repository.get_by_id(academy_id)
        if academy is None:
            raise NotFoundException("Academy not found")
        if academy.company_type != CompanyType.ACADEMY.value:
            raise BadRequestException(f"Company {academy_id} is not an academy.")
        return academy

    def get_academy_members(self, academy_id: int, filters) -> tuple[list[Company], int]:
        """Companies attached to this academy. 404 if the academy doesn't exist."""
        self._get_academy(academy_id)
        filters.academy_id = academy_id  # overrides any client-sent value
        return self.repository.get_list(filters=filters)

    def add_company_to_academy(self, academy_id: int, company_id: int) -> Company:
        self._get_academy(academy_id)

        if company_id == academy_id:
            raise BadRequestException("An academy cannot be a member of itself.")

        company = self.repository.get_by_id(company_id)
        if company is None:
            raise NotFoundException("Company not found")
        if company.company_type == CompanyType.ACADEMY.value:
            raise BadRequestException("An academy cannot belong to another academy.")
        if company.academy_id == academy_id:
            raise ConflictException("Company is already in this academy.")
        if company.academy_id is not None:
            raise ConflictException(
                "Company already belongs to another academy — remove it from that one first."
            )

        return self.repository.update(company_id, {"academy_id": academy_id})

    def remove_company_from_academy(self, academy_id: int, company_id: int) -> Company:
        self._get_academy(academy_id)

        company = self.repository.get_by_id(company_id)
        if company is None:
            raise NotFoundException("Company not found")
        if company.academy_id != academy_id:
            raise NotFoundException("Company is not a member of this academy.")

        return self.repository.update(company_id, {"academy_id": None})
