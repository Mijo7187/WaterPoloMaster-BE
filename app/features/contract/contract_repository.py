# ============================================
# CONTRACT REPOSITORY - Database Operations
# ============================================

from datetime import date
from typing import Any, List

from sqlalchemy import and_, false, or_
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.contract.contract_model import (
    Contract,
    ContractStatus,
    ContractType,
)
from app.features.contract_installment.contract_installment_model import (
    ContractInstallment,
)
from app.features.season.season_model import Season


class ContractRepository(CrudRepository[Contract]):
    def __init__(self, db: Session):
        super().__init__(db, Contract)

    def get_list_relations(self):
        return [
            lambda: selectinload(Contract.user),
            lambda: selectinload(Contract.membership),
        ]

    def _apply_filter(self, q, key: str, value: Any):
        """Intercept `season_id` before the generic parser sees it.

        `contract` has no season_id column, so CrudRepository._apply_filter
        would silently skip the filter and return an unfiltered list.

        A season's members are the contracts whose active period OVERLAPS the
        season. A contract is not pinned to a season at all - it carries its
        own start_date and end_date - so the overlap is the only sensible
        reading, and it keeps open-ended (end_date NULL) contracts included.
        """
        if key == "season_id":
            season = self.db.get(Season, value)
            if season is None:
                return q.filter(false())
            return q.filter(
                Contract.start_date <= season.end_date,
                or_(
                    Contract.end_date.is_(None),
                    Contract.end_date >= season.start_date,
                ),
            )
        return super()._apply_filter(q, key, value)

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Contract.user),
            lambda: selectinload(Contract.membership),
            lambda: selectinload(Contract.installments),
        ]

    def apply_create_relations(self, db_obj: Contract, data: dict) -> None:
        """Turn `installments_list` into contract_installment rows.

        The service has already validated and normalized the list (see
        _resolve_installments), so this only materializes it.
        """
        for item in data.pop("installments_list", None) or []:
            db_obj.installments.append(ContractInstallment(**item))

    def get_active_staff_for_month(
        self, month_start: date, month_end: date
    ) -> List[Contract]:
        """ACTIVE STAFF contracts covering any day of [month_start, month_end].

        What the monthly salary job pays. STAFF only, deliberately — a
        MEMBERSHIP's schedule is fixed at signing, and generating more would
        auto-renew a membership nobody signed.
        """
        return (
            self.db.query(Contract)
            .filter(
                Contract.status == ContractStatus.ACTIVE,
                Contract.contract_type == ContractType.STAFF,
                Contract.start_date <= month_end,
                or_(Contract.end_date.is_(None), Contract.end_date >= month_start),
            )
            .order_by(Contract.id.asc())
            .all()
        )

    def get_stale_status(self, today: date) -> List[Contract]:
        """Contracts whose stored status the dates have moved past on `today`.

        DRAFT that has started (→ ACTIVE or ENDED) and ACTIVE whose end_date
        has passed (→ ENDED). CANCELLED and ENDED are never touched. Drives the
        daily status job.
        """
        return (
            self.db.query(Contract)
            .filter(
                or_(
                    and_(
                        Contract.status == ContractStatus.DRAFT,
                        Contract.start_date <= today,
                    ),
                    and_(
                        Contract.status == ContractStatus.ACTIVE,
                        Contract.end_date.isnot(None),
                        Contract.end_date < today,
                    ),
                )
            )
            .order_by(Contract.id.asc())
            .all()
        )

    def get_active_for_user(self, user_id: int, on_date: date) -> List[Contract]:
        """Active contracts covering a date. An end_date of NULL is open-ended."""
        return (
            self.db.query(Contract)
            .filter(
                Contract.user_id == user_id,
                Contract.status == ContractStatus.ACTIVE,
                Contract.start_date <= on_date,
                or_(Contract.end_date.is_(None), Contract.end_date >= on_date),
            )
            .all()
        )
