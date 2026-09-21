from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.payment.payment_model import (
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
        if key == "wallet_id":
            return q.filter(
                or_(
                    Payment.sender_wallet_id == value,
                    Payment.receiver_wallet_id == value,
                )
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
        or its contract is cancelled. Only PENDING rows; settled money stays."""
        self.db.query(Payment).filter(
            Payment.sender_wallet_id == sender_wallet_id,
            Payment.payable_type == PayableType.CONTRACT_INSTALLMENT,
            Payment.payable_id == installment_id,
            Payment.payment_type == PaymentTypeCode.USER_MEMBERSHIP_FEE,
            Payment.status == PaymentStatus.PENDING,
        ).delete(synchronize_session=False)
        self.db.commit()
