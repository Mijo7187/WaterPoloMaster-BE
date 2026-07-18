from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.company.company_model import Company
from app.features.payment.payment_model import Payment, PaymentStatus, PaymentTypeCode
from app.features.quarter.quarter_model import Quarter
from app.features.tournament.tournament_model import Tournament
from app.features.training.training_model import Training


def _payment_relations():
    """Eager loads shared by list and by-id.

    The nested quarter/tournament/training objects are serialized with the same
    lightweight schemas their own list endpoints use, so we mirror those
    endpoints' eager loads here (users lists for the derived counts, and
    company/pool with their city/country) to avoid any lazy load after the
    session closes."""
    return [
        lambda: selectinload(Payment.sender_wallet),
        lambda: selectinload(Payment.receiver_wallet),
        # quarter -> QuarterListResponse (quarter_users counts, company+city/country)
        lambda: selectinload(Payment.quarter).selectinload(Quarter.quarter_users),
        lambda: selectinload(Payment.quarter)
        .selectinload(Quarter.company)
        .selectinload(Company.city),
        lambda: selectinload(Payment.quarter)
        .selectinload(Quarter.company)
        .selectinload(Company.country),
        # tournament -> TournamentListResponse (users count, company/pool, quarter_type)
        lambda: selectinload(Payment.tournament).selectinload(Tournament.tournament_users),
        lambda: selectinload(Payment.tournament)
        .selectinload(Tournament.company)
        .selectinload(Company.city),
        lambda: selectinload(Payment.tournament)
        .selectinload(Tournament.company)
        .selectinload(Company.country),
        lambda: selectinload(Payment.tournament)
        .selectinload(Tournament.pool)
        .selectinload(Company.city),
        lambda: selectinload(Payment.tournament)
        .selectinload(Tournament.pool)
        .selectinload(Company.country),
        lambda: selectinload(Payment.tournament).selectinload(Tournament.quarter),
        # training -> TrainingListResponse (players count, company/pool, type, quarter_type)
        lambda: selectinload(Payment.training).selectinload(Training.training_users),
        lambda: selectinload(Payment.training)
        .selectinload(Training.company)
        .selectinload(Company.city),
        lambda: selectinload(Payment.training)
        .selectinload(Training.company)
        .selectinload(Company.country),
        lambda: selectinload(Payment.training)
        .selectinload(Training.pool)
        .selectinload(Company.city),
        lambda: selectinload(Payment.training)
        .selectinload(Training.pool)
        .selectinload(Company.country),
        lambda: selectinload(Payment.training).selectinload(Training.quarter),
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

    def get_list(self, filters):
        # Default to newest first (payment id is a random UUID, so the generic
        # id-based fallback order is meaningless here). An explicit order_by from
        # the client still wins.
        if not filters.order_by:
            filters = filters.model_copy(
                update={"order_by": "created_at", "order_dir": "desc"}
            )
        return super().get_list(filters)

    def delete_pending_quarterly_fee(self, sender_wallet_id, quarter_id: int) -> None:
        self.db.query(Payment).filter(
            Payment.sender_wallet_id == sender_wallet_id,
            Payment.quarter_id == quarter_id,
            Payment.payment_type == PaymentTypeCode.USER_QUARTERLY_FEE,
            Payment.status == PaymentStatus.PENDING,
        ).delete(synchronize_session=False)
        self.db.commit()
