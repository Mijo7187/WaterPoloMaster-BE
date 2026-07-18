from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.payment.payment_model import Payment
from app.features.quarter_users.quarter_users_model import QuarterUsers
from app.features.users.users_models import User
from app.features.wallet.wallet_model import Wallet, WalletOwnerType


class QuarterUsersRepository(CrudRepository[QuarterUsers]):
    def __init__(self, db: Session):
        super().__init__(db, QuarterUsers)

    def get_list_relations(self):
        return [
            lambda: selectinload(QuarterUsers.user),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(QuarterUsers.user),
        ]

    def get_list_with_payment_status(self, filters):
        """
        Same list/filter/pagination behavior as the generic get_list, but each row is
        returned as a (QuarterUsers, payment_status) tuple. payment_status is resolved via
        a correlated scalar subquery over the wallet → payment join — one SQL query, no
        N+1. Correlates on the row's own quarter_id so the status is per-row correct even
        when the list spans multiple quarters.
        """
        filter_dict = filters.model_dump(exclude_unset=True)
        page = filter_dict.pop("page", filters.page)
        size = filter_dict.pop("size", filters.size)
        order_by_field = filter_dict.pop("order_by", None)
        order_dir = filter_dict.pop("order_dir", "asc")
        offset = (page - 1) * size

        payment_status_subq = (
            select(Payment.status)
            .join(Wallet, Payment.sender_wallet_id == Wallet.id)
            .where(
                Wallet.owner_id == QuarterUsers.user_id,
                Wallet.owner_type == WalletOwnerType.USER,
                Payment.quarter_id == QuarterUsers.quarter_id,
            )
            .correlate(QuarterUsers)
            .scalar_subquery()
        )

        conditions = []
        for key, value in filter_dict.items():
            if value is None:
                continue
            if hasattr(QuarterUsers, key):
                conditions.append(getattr(QuarterUsers, key) == value)

        if order_by_field and hasattr(QuarterUsers, order_by_field):
            col = getattr(QuarterUsers, order_by_field)
            order_clause = col.desc() if order_dir == "desc" else col.asc()
        else:
            order_clause = QuarterUsers.id.asc()

        total = self.db.execute(
            select(func.count()).select_from(QuarterUsers).where(*conditions)
        ).scalar_one()

        stmt = (
            select(QuarterUsers, payment_status_subq.label("payment_status"))
            .options(joinedload(QuarterUsers.user))
            .where(*conditions)
            .order_by(order_clause)
            .offset(offset)
            .limit(size)
        )
        rows = self.db.execute(stmt).all()
        return rows, total

    def get_users_not_in_quarter(self, quarter_id: int, company_id: int, page: int = 1, size: int = 20):
        subq = (
            self.db.query(QuarterUsers.user_id)
            .filter(QuarterUsers.quarter_id == quarter_id)
            .subquery()
        )
        q = self.db.query(User).filter(
            ~User.id.in_(subq),
            User.company_id == company_id,
        )
        total = q.count()
        items = q.offset((page - 1) * size).limit(size).all()
        return items, total
