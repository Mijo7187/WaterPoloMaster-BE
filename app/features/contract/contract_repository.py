# ============================================
# CONTRACT REPOSITORY - Database Operations
# ============================================

from datetime import date
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import and_, case, false, func, or_
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.contract.contract_model import (
    Contract,
    ContractStatus,
    ContractType,
)
from app.features.membership.membership_model import BillingType, Membership
from app.features.season.season_model import Season


class ContractRepository(CrudRepository[Contract]):
    def __init__(self, db: Session):
        super().__init__(db, Contract)

    def get_list_relations(self):
        return [
            lambda: selectinload(Contract.user),
            # Chained: the nested membership carries its own selection.
            lambda: selectinload(Contract.membership).selectinload(
                Membership.selection
            ),
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

    def get_summary(self, filters, company_id=None) -> Optional[dict]:
        q = self.list_query(filters, company_id)

        by_status = {s.value: 0 for s in ContractStatus}
        for status, n in (
            q.with_entities(Contract.status, func.count(Contract.id))
            .group_by(Contract.status)
            .all()
        ):
            by_status[ContractStatus(status).value] = n

        def recurring(*conds):
            return func.coalesce(
                func.sum(
                    case((and_(Contract.status == ContractStatus.ACTIVE, *conds), Contract.amount), else_=0)
                ),
                0,
            )

        income, outcome = q.with_entities(
            recurring(
                Contract.contract_type == ContractType.MEMBERSHIP,
                Contract.billing_type == BillingType.MONTHLY,
            ),
            recurring(Contract.contract_type == ContractType.STAFF),
        ).one()

        return {
            "count": sum(by_status.values()),
            "by_status": by_status,
            "monthly_income": Decimal(str(income or 0)),
            "monthly_outcome": Decimal(str(outcome or 0)),
        }

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Contract.user),
            lambda: selectinload(Contract.membership).selectinload(
                Membership.selection
            ),
            lambda: selectinload(Contract.installments),
        ]

    def get_active_recurring_for_month(
        self, month_start: date, month_end: date
    ) -> List[Contract]:
        """ACTIVE recurring contracts covering any day of [month_start, month_end].

        What the monthly recurring billing job pays: STAFF salaries and
        MEMBERSHIP MONTHLY dues, which are the same shape — one period of
        `amount` per ACTIVE month.

        MEMBERSHIP TERM is excluded deliberately. Its single block installment
        is written once at activation; generating more would auto-renew a block
        nobody signed. The next block is a new contract.
        """
        return (
            self.db.query(Contract)
            .filter(
                Contract.status == ContractStatus.ACTIVE,
                or_(
                    Contract.contract_type == ContractType.STAFF,
                    and_(
                        Contract.contract_type == ContractType.MEMBERSHIP,
                        Contract.billing_type == BillingType.MONTHLY,
                    ),
                ),
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
