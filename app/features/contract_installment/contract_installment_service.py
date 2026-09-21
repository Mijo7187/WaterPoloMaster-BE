# ============================================
# CONTRACT INSTALLMENT SERVICE - Business Logic
# ============================================

from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudHooks
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.features.contract.contract_model import Contract
from app.features.contract_installment.contract_installment_model import (
    ContractInstallment,
)
from app.features.contract_installment.contract_installment_repository import (
    ContractInstallmentRepository,
)
from app.features.payment.payment_repository import PaymentRepository
from app.features.users.users_models import User, UserRole
from app.features.wallet.wallet_model import WalletOwnerType
from app.features.wallet.wallet_repository import WalletRepository


def _enforce_contract_company(
    contract: Optional[Contract], current_user: Optional[User]
) -> None:
    """Row-level company scoping, resolved through the parent contract."""
    if current_user is None or contract is None:
        return
    if UserRole.SUPER_ADMIN.value in (current_user.roles or []):
        return
    if contract.company_id != current_user.company_id:
        raise ForbiddenException(
            "You can only edit installments in your own company."
        )


def _validate_row(
    db, contract_id: int, row_id: Optional[int], period_start, period_end
) -> None:
    """One row must be a valid period and must not overlap any other row of
    the same contract — the same rules as installments_list at contract create.
    """
    if period_end < period_start:
        raise ValidationException(
            ["period_end"], "period_end must be on or after period_start."
        )

    for other in ContractInstallmentRepository(db).get_for_contract(contract_id):
        if other.id == row_id:
            continue
        if other.period_start <= period_end and period_start <= other.period_end:
            raise ValidationException(
                ["period_start"],
                f"This period overlaps installment {other.id} "
                f"({other.period_start} - {other.period_end}).",
            )


def _installment_pre_create(data: dict, db, current_user: Optional[User] = None) -> dict:
    contract = db.get(Contract, data.get("contract_id"))
    if not contract:
        raise NotFoundException("Contract not found")
    _enforce_contract_company(contract, current_user)

    _validate_row(db, contract.id, None, data["period_start"], data["period_end"])
    return data


def _installment_pre_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    existing = db.get(ContractInstallment, obj_id)
    if not existing:
        return data  # CrudService raises NotFoundException
    _enforce_contract_company(existing.contract, current_user)

    if "period_start" in data or "period_end" in data:
        _validate_row(
            db,
            existing.contract_id,
            existing.id,
            data.get("period_start") or existing.period_start,
            data.get("period_end") or existing.period_end,
        )
    return data


def _sync_contract(obj: ContractInstallment, db, current_user: Optional[User] = None) -> None:
    """post_create / post_update: a MEMBERSHIP contract's amount / start_date /
    end_date are its installments' sum / first period_start / last
    period_end — re-derive them (and the status) after a single row changes."""
    # Imported here: contract_service imports this feature's repository.
    from app.features.contract.contract_service import ContractService

    contract = db.get(Contract, obj.contract_id)
    if contract:
        ContractService(db).sync_from_installments(contract)


class ContractInstallmentService(CrudService[ContractInstallment]):
    def __init__(self, db: Session):
        super().__init__(
            db,
            ContractInstallmentRepository(db),
            hooks=CrudHooks(
                pre_create=_installment_pre_create,
                pre_update=_installment_pre_update,
                post_create=_sync_contract,
                post_update=_sync_contract,
            ),
        )

    # ------------------------------------------------------------------
    # Computed payment state — never stored
    # ------------------------------------------------------------------

    def attach_payment_state(self, rows: List[ContractInstallment]) -> None:
        """Set `.paid_amount` and `.payment_status` on each row.

        Derived from COMPLETED payments pointing at the installment, in one
        grouped query for the whole page. `waived` short-circuits: a waived
        period is settled by decision, not by money. A 0-amount row (a
        scholarship) owes nothing, so it is "paid".
        """
        paid = self.repository.paid_amounts_for([r.id for r in rows])

        for row in rows:
            amount_paid = paid.get(row.id, Decimal("0"))
            row.paid_amount = amount_paid

            if row.waived:
                row.payment_status = "waived"
            elif Decimal(row.amount) <= 0:
                row.payment_status = "paid"
            elif amount_paid <= 0:
                row.payment_status = "pending"
            elif amount_paid < Decimal(row.amount):
                row.payment_status = "partial"
            else:
                row.payment_status = "paid"

    def get_list(self, filters, company_id: Optional[int] = None):
        items, total = self.repository.get_list(filters, company_id=company_id)
        self.attach_payment_state(items)
        return items, total

    def get_by_id(self, obj_id: int, company_id: Optional[int] = None) -> ContractInstallment:
        obj = super().get_by_id(obj_id, company_id=company_id)
        self.attach_payment_state([obj])
        return obj

    # ------------------------------------------------------------------

    def waive(self, obj_id: int, current_user: Optional[User] = None) -> ContractInstallment:
        """
        Waive a single period: the club forgives this one due.

        Any PENDING payment already raised for it is dropped — settled money is
        left alone, since waiving is forward-looking, not a refund.
        """
        obj = self.db.get(ContractInstallment, obj_id)
        if not obj:
            raise NotFoundException("Contract installment not found")

        if current_user is not None and UserRole.SUPER_ADMIN.value not in (
            current_user.roles or []
        ):
            if obj.contract and obj.contract.company_id != current_user.company_id:
                raise ForbiddenException(
                    "You can only waive installments in your own company."
                )

        contract: Contract = obj.contract
        if contract:
            spec = contract.spec
            owner_id = (
                contract.user_id
                if spec.sender_type == WalletOwnerType.USER
                else contract.company_id
            )
            sender_wallet = WalletRepository(self.db).get_by_owner(
                owner_id, spec.sender_type
            )
            if sender_wallet:
                PaymentRepository(self.db).delete_pending_membership_fee(
                    sender_wallet.id, obj.id
                )

        obj.waived = True
        self.db.commit()
        self.db.refresh(obj)
        self.attach_payment_state([obj])
        return obj

    def delete(self, obj_id: int) -> None:
        obj = self.db.get(ContractInstallment, obj_id)
        if not obj:
            raise NotFoundException("Contract installment not found")
        contract_id = obj.contract_id
        self.db.delete(obj)
        self.db.commit()
        contract = self.db.get(Contract, contract_id)
        if contract:
            # Imported here: contract_service imports this feature's repository.
            from app.features.contract.contract_service import ContractService

            ContractService(self.db).sync_from_installments(contract)
