from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.payment.payment_model import PayableType, Payment
from app.features.tournament_users.tournament_users_model import TournamentUsers
from app.features.users.users_models import User
from app.features.wallet.wallet_model import Wallet, WalletOwnerType


class TournamentUsersRepository(CrudRepository[TournamentUsers]):
    def __init__(self, db: Session):
        super().__init__(db, TournamentUsers)

    def get_list_relations(self):
        return [
            lambda: selectinload(TournamentUsers.user),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(TournamentUsers.user),
        ]

    def get_list_with_payment_status(self, filters):
        """
        Same list/filter/pagination behavior as the generic get_list, but each row is
        returned as a (TournamentUsers, payment_status) tuple. payment_status is resolved
        via a correlated scalar subquery over the wallet → payment join — one SQL query,
        no N+1. Correlates on the row's own tournament_id so the status is per-row correct
        even when the list spans multiple tournaments.

        The payment side is matched on the polymorphic (payable_type, payable_id)
        pair — payment no longer carries a tournament_id column.
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
                Wallet.owner_id == TournamentUsers.user_id,
                Wallet.owner_type == WalletOwnerType.USER,
                Payment.payable_type == PayableType.TOURNAMENT,
                Payment.payable_id == TournamentUsers.tournament_id,
            )
            .correlate(TournamentUsers)
            .scalar_subquery()
        )

        conditions = []
        for key, value in filter_dict.items():
            if value is None:
                continue
            if hasattr(TournamentUsers, key):
                conditions.append(getattr(TournamentUsers, key) == value)

        if order_by_field and hasattr(TournamentUsers, order_by_field):
            col = getattr(TournamentUsers, order_by_field)
            order_clause = col.desc() if order_dir == "desc" else col.asc()
        else:
            order_clause = TournamentUsers.id.asc()

        total = self.db.execute(
            select(func.count()).select_from(TournamentUsers).where(*conditions)
        ).scalar_one()

        stmt = (
            select(TournamentUsers, payment_status_subq.label("payment_status"))
            .options(joinedload(TournamentUsers.user))
            .where(*conditions)
            .order_by(order_clause)
            .offset(offset)
            .limit(size)
        )
        rows = self.db.execute(stmt).all()
        return rows, total

    def get_users_not_in_tournament(self, tournament_id: int, company_id: int, page: int = 1, size: int = 20):
        subq = (
            self.db.query(TournamentUsers.user_id)
            .filter(TournamentUsers.tournament_id == tournament_id)
            .subquery()
        )
        q = self.db.query(User).filter(
            ~User.id.in_(subq),
            User.company_id == company_id,
        )
        total = q.count()
        items = q.offset((page - 1) * size).limit(size).all()
        return items, total
