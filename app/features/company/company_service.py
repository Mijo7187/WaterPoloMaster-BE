from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudHooks
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
        hooks = CrudHooks(pre_update=self._guard_academy_on_update)
        super().__init__(db, CompanyRepository(db), hooks=hooks)

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
        if data.get("academy_id") is not None:
            self._guard_academy_write(
                data["academy_id"], data.get("company_type"), current_user=current_user
            )
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
    # It can be set two ways, and both land on the same validation:
    #   • the dedicated /academy endpoints — add/remove a named member
    #   • academy_id on company create/update — set it alongside other fields
    # The difference is re-homing: /academy/{id}/companies refuses a company
    # that already belongs elsewhere (409, remove it first), while a direct
    # write treats a changed academy_id as a deliberate move.

    def _guard_academy_write(
        self,
        academy_id: Optional[int],
        company_type: Optional[str],
        current_user: Optional[Any] = None,
        company_id: Optional[int] = None,
    ) -> None:
        """
        Validate an academy_id arriving through company create/update, so the
        direct path cannot reach states the /academy endpoints refuse.

        current_user is None → internal call (test, seed, background job);
        HTTP auth is enforced upstream by check_permissions.
        """
        from app.core.permissions import is_super_admin

        # Same bar as the /academy endpoints: membership is SUPER_ADMIN-only.
        # Without this, CREATE/UPDATE_COMPANY would be enough for an ADMIN to
        # attach their own club to any academy.
        if current_user is not None and not is_super_admin(current_user):
            raise ForbiddenException("Only a SUPER_ADMIN can change academy membership.")

        if academy_id is None:
            return  # detaching — nothing left to validate

        self._get_academy(academy_id)

        if company_id is not None and company_id == academy_id:
            raise BadRequestException("An academy cannot be a member of itself.")
        if company_type == CompanyType.ACADEMY.value:
            raise BadRequestException("An academy cannot belong to another academy.")

    def _guard_academy_on_update(
        self,
        obj_id: int,
        data: dict,
        db: Session,
        current_user: Optional[Any] = None,
    ) -> dict:
        """pre_update hook — only fires when the payload actually carries academy_id."""
        if "academy_id" not in data:
            return data

        # The type the row will have after this update, not necessarily the stored one.
        company_type = data.get("company_type")
        if company_type is None:
            existing = self.repository.get_by_id(obj_id)
            company_type = existing.company_type if existing else None

        self._guard_academy_write(
            data["academy_id"],
            company_type,
            current_user=current_user,
            company_id=obj_id,
        )
        return data

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
