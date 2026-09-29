from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.contract_installment.contract_installment_model import (
    ContractInstallment,
)
from app.features.payment.payment_model import (
    OUTSTANDING_STATUSES,
    PAYMENT_TYPE_SPECS,
    PayableType,
    Payment,
    PaymentStatus,
    PaymentTypeCode,
)
from app.features.users.users_models import User
from app.features.wallet.wallet_model import Wallet, WalletOwnerType


def _payment_relations():
    """Eager loads shared by list and by-id.

    Only the wallets are real relationships now. The payable
    (contract_installment / tournament / training) is polymorphic and has no
    relationship to load — it is resolved in one batched pass per type by
    app/common/resolver/polymorphic_resolver.py, which also carries the nested
    eager loads each payable's list schema needs.
    """
    return [
        lambda: selectinload(Payment.sender_wallet),
        lambda: selectinload(Payment.receiver_wallet),
    ]


class PaymentRepository(CrudRepository[Payment]):
    def __init__(self, db: Session):
        super().__init__(db, Payment)

    def get_list_relations(self):
        return _payment_relations()

    def get_by_id_relations(self):
        return _payment_relations()

    def _apply_filter(self, q, key, value):
        # `wallet_id` is a virtual filter (no such column): match payments where the
        # wallet is either the sender OR the receiver. Everything else falls through
        # to the generic per-field (AND) filtering.
        # `second_wallet_id` is the same OR, ANDed with wallet_id's — together they
        # leave only payments between the two wallets, in either direction.
        if key in ("wallet_id", "second_wallet_id"):
            return q.filter(
                or_(
                    Payment.sender_wallet_id == value,
                    Payment.receiver_wallet_id == value,
                )
            )
        # `date_from` / `date_to` are whole calendar days, both inclusive:
        # date_to=2026-09-30 keeps everything created on the 30th.
        if key == "date_from":
            return q.filter(Payment.created_at >= datetime.combine(value, time.min))
        if key == "date_to":
            return q.filter(
                Payment.created_at < datetime.combine(value + timedelta(days=1), time.min)
            )
        return super()._apply_filter(q, key, value)

    # ── Company scope ────────────────────────────────
    # Payment has no company_id column. A payment belongs to a company when
    # either side of it is a wallet of that company or of one of its users.

    def _company_wallet_ids(self, company_id: int):
        return select(Wallet.id).where(
            or_(
                and_(
                    Wallet.owner_type == WalletOwnerType.COMPANY,
                    Wallet.owner_id == company_id,
                ),
                and_(
                    Wallet.owner_type == WalletOwnerType.USER,
                    Wallet.owner_id.in_(select(User.id).where(User.company_id == company_id)),
                ),
            )
        )

    def _apply_company_scope(self, q, company_id):
        if company_id is None:
            return q
        wallet_ids = self._company_wallet_ids(company_id)
        return q.filter(
            or_(
                Payment.sender_wallet_id.in_(wallet_ids),
                Payment.receiver_wallet_id.in_(wallet_ids),
            )
        )

    def wallet_in_company(self, wallet_id, company_id: int) -> bool:
        return (
            self.db.query(Wallet.id)
            .filter(Wallet.id == wallet_id, Wallet.id.in_(self._company_wallet_ids(company_id)))
            .first()
            is not None
        )

    def get_list(self, filters, company_id=None):
        # Default to newest first (payment id is a random UUID, so the generic
        # id-based fallback order is meaningless here). An explicit order_by from
        # the client still wins.
        if not filters.order_by:
            filters = filters.model_copy(
                update={"order_by": "created_at", "order_dir": "desc"}
            )
        return super().get_list(filters, company_id=company_id)

    def _summary_sides(self, filters, company_id):
        """(received, sent) conditions deciding what counts as income/outcome.

        - ?wallet_id=  → that wallet's side.
        - company scope (ADMIN) → the company's own wallet(s). Its users'
          wallets are in scope but are the counterparty, not "us".
        - neither (SUPER_ADMIN, whole app) → the clubs' side, by payment type
          direction from PAYMENT_TYPE_SPECS: user → company is income,
          anything a company pays out is outcome.
        """
        if filters.wallet_id is not None:
            return (
                Payment.receiver_wallet_id == filters.wallet_id,
                Payment.sender_wallet_id == filters.wallet_id,
            )
        if company_id is not None:
            own = select(Wallet.id).where(
                Wallet.owner_type == WalletOwnerType.COMPANY,
                Wallet.owner_id == company_id,
            )
            return (
                Payment.receiver_wallet_id.in_(own),
                Payment.sender_wallet_id.in_(own),
            )
        income_types = [
            code for code, spec in PAYMENT_TYPE_SPECS.items()
            if spec.sender_type == WalletOwnerType.USER
            and spec.receiver_type == WalletOwnerType.COMPANY
        ]
        outcome_types = [
            code for code, spec in PAYMENT_TYPE_SPECS.items()
            if spec.sender_type == WalletOwnerType.COMPANY
        ]
        return (
            Payment.payment_type.in_(income_types),
            Payment.payment_type.in_(outcome_types),
        )

    def get_summary(self, filters, company_id=None) -> Optional[dict]:
        """Income / outcome / pending / debt over the filtered list.

        One aggregate over list_query, so it honours every list filter and the
        company scope. Whose side "income" is seen from: see _summary_sides.
        """
        received, sent = self._summary_sides(filters, company_id)

        def bucket(status, side):
            return func.coalesce(
                func.sum(case((and_(Payment.status == status, side), Payment.amount), else_=0)),
                0,
            )

        row = (
            self.list_query(filters, company_id)
            .with_entities(
                bucket(PaymentStatus.COMPLETED, received),
                bucket(PaymentStatus.COMPLETED, sent),
                bucket(PaymentStatus.PENDING, received),
                bucket(PaymentStatus.PENDING, sent),
                bucket(PaymentStatus.DEBT, sent),
                bucket(PaymentStatus.DEBT, received),
                func.count(Payment.id),
            )
            .one()
        )
        income, outcome, pending_in, pending_out, debt, receivable = (
            Decimal(str(v or 0)) for v in row[:6]
        )
        count = row[6]
        return {
            "total_income": income,
            "total_outcome": outcome,
            "balance": income - outcome,
            "pending_income": pending_in,
            "pending_outcome": pending_out,
            "total_debt": debt,
            "debt_receivable": receivable,
            "count": count,
        }

    def paid_payable_ids(self, payable_type: PayableType) -> set:
        """Ids of payables that already have a payment of this type.

        Used by the billing/training jobs to stay idempotent without an N+1
        existence check per candidate row.
        """
        rows = (
            self.db.query(Payment.payable_id)
            .filter(
                Payment.payable_type == payable_type,
                Payment.payable_id.isnot(None),
            )
            .all()
        )
        return {row[0] for row in rows}

    def delete_pending_membership_fee(self, sender_wallet_id, installment_id: int) -> None:
        """Drop an unpaid membership due — e.g. when its installment is waived
        or its contract is cancelled. Only unsettled rows; settled money stays.

        DEBT counts as unsettled: an overdue due is still just an unpaid due,
        and waiving its installment must clear it too.
        """
        self.db.query(Payment).filter(
            Payment.sender_wallet_id == sender_wallet_id,
            Payment.payable_type == PayableType.CONTRACT_INSTALLMENT,
            Payment.payable_id == installment_id,
            Payment.payment_type == PaymentTypeCode.USER_MEMBERSHIP_FEE,
            Payment.status.in_(OUTSTANDING_STATUSES),
        ).delete(synchronize_session=False)
        self.db.commit()

    def get_pending_past_due(self, on_date: date) -> List[Payment]:
        """PENDING installment dues whose due date has passed on `on_date`.

        What the daily debt job flips to DEBT. Joined to contract_installment
        because the due date lives there, not on the payment — which also
        means payables with no due date (a training, a tournament) are never
        swept up. A waived installment is excluded: it is settled by decision.
        """
        return (
            self.db.query(Payment)
            .join(
                ContractInstallment,
                Payment.payable_id == ContractInstallment.id,
            )
            .filter(
                Payment.payable_type == PayableType.CONTRACT_INSTALLMENT,
                Payment.status == PaymentStatus.PENDING,
                ContractInstallment.due_date < on_date,
                ContractInstallment.waived.is_(False),
            )
            .order_by(ContractInstallment.due_date.asc())
            .all()
        )
