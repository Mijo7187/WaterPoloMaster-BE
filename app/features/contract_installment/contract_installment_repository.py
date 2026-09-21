# ============================================
# CONTRACT INSTALLMENT REPOSITORY - Database Operations
# ============================================

from datetime import date
from decimal import Decimal
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.contract.contract_model import Contract, ContractStatus
from app.features.contract_installment.contract_installment_model import (
    ContractInstallment,
)
from app.features.payment.payment_model import PayableType, Payment, PaymentStatus


class ContractInstallmentRepository(CrudRepository[ContractInstallment]):
    def __init__(self, db: Session):
        super().__init__(db, ContractInstallment)

    def company_scope_clause(self, company_id: int):
        """No company_id column — an installment belongs to its contract's company."""
        return ContractInstallment.contract_id.in_(
            select(Contract.id).where(Contract.company_id == company_id)
        )

    def get_for_contract(self, contract_id: int) -> List[ContractInstallment]:
        """Every installment of one contract, ordered by period_start."""
        return (
            self.db.query(ContractInstallment)
            .filter(ContractInstallment.contract_id == contract_id)
            .order_by(ContractInstallment.period_start.asc())
            .all()
        )

    def get_by_id_relations(self):
        return [
            lambda: selectinload(ContractInstallment.contract),
        ]

    def _already_billed_ids(self):
        """Subquery of installment ids that already have a payment pointing at them."""
        return (
            self.db.query(Payment.payable_id)
            .filter(
                Payment.payable_type == PayableType.CONTRACT_INSTALLMENT,
                Payment.payable_id.isnot(None),
            )
            .subquery()
        )

    def get_due_unbilled(self, on_date: date) -> List[ContractInstallment]:
        """
        Installments whose due date has arrived and that have no payment yet.

        Drives the nightly billing job. Excludes waived and 0-amount rows and
        any contract that is not ACTIVE. The NOT EXISTS keeps the job idempotent in a single
        query rather than an existence check per row.
        """
        return (
            self.db.query(ContractInstallment)
            .join(Contract, ContractInstallment.contract_id == Contract.id)
            .options(selectinload(ContractInstallment.contract))
            .filter(
                ContractInstallment.due_date <= on_date,
                ContractInstallment.waived.is_(False),
                # A 0 installment (scholarship) is owed nothing — never billed.
                ContractInstallment.amount > 0,
                Contract.status == ContractStatus.ACTIVE,
                ~ContractInstallment.id.in_(self._already_billed_ids()),
            )
            .order_by(ContractInstallment.due_date.asc())
            .all()
        )

    def get_unbilled_for_contract(self, contract_id: int) -> List[ContractInstallment]:
        """
        Every unwaived installment of one contract that has no payment yet,
        whatever its due date or the contract's status.

        Drives settling a contract when it ENDS — future periods included.
        """
        return (
            self.db.query(ContractInstallment)
            .options(selectinload(ContractInstallment.contract))
            .filter(
                ContractInstallment.contract_id == contract_id,
                ContractInstallment.waived.is_(False),
                ContractInstallment.amount > 0,
                ~ContractInstallment.id.in_(self._already_billed_ids()),
            )
            .order_by(ContractInstallment.due_date.asc())
            .all()
        )

    def latest_period_end(self, contract_id: int) -> Optional[date]:
        """The end of the last period already generated, or None if there are none.

        Where an open-ended contract's rolling generation picks up from.
        """
        return (
            self.db.query(func.max(ContractInstallment.period_end))
            .filter(ContractInstallment.contract_id == contract_id)
            .scalar()
        )

    def paid_amounts_for(self, installment_ids: Iterable[int]) -> Dict[int, Decimal]:
        """
        Sum of COMPLETED payments per installment — one grouped query, no N+1.

        paid/pending/partial is COMPUTED from this, never stored. `waived` is
        the only stored payment-state on an installment.
        """
        ids = list(installment_ids)
        if not ids:
            return {}

        rows = (
            self.db.query(
                Payment.payable_id,
                func.coalesce(func.sum(Payment.amount), 0),
            )
            .filter(
                Payment.payable_type == PayableType.CONTRACT_INSTALLMENT,
                Payment.payable_id.in_(ids),
                Payment.status == PaymentStatus.COMPLETED,
            )
            .group_by(Payment.payable_id)
            .all()
        )
        return {row[0]: Decimal(row[1] or 0) for row in rows}
