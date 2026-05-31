import uuid
from decimal import Decimal
from typing import List

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import NotFoundException
from app.features.company.company_model import Company
from app.features.payment.payment_model import Payment, PaymentStatus
from app.features.users.users_models import User
from app.features.wallet.wallet_model import Wallet, WalletOwnerType
from app.features.wallet.wallet_repository import WalletRepository
from app.features.wallet.wallet_schemas import LedgerEntry


class WalletService(CrudService[Wallet]):
    def __init__(self, db: Session):
        super().__init__(db, WalletRepository(db))

    def resolve_owner(self, wallet: Wallet) -> User | Company:
        if wallet.owner_type == WalletOwnerType.USER:
            owner = self.db.get(User, wallet.owner_id)
        else:
            owner = self.db.get(Company, wallet.owner_id)
        if not owner:
            raise NotFoundException("Wallet owner not found")
        return owner

    def get_summary(self, wallet_id: uuid.UUID) -> dict:
        total_in_completed = Decimal(
            self.db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(
                Payment.receiver_wallet_id == wallet_id,
                Payment.status == PaymentStatus.COMPLETED,
            )
            .scalar() or 0
        )
        total_out_completed = Decimal(
            self.db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(
                Payment.sender_wallet_id == wallet_id,
                Payment.status == PaymentStatus.COMPLETED,
            )
            .scalar() or 0
        )
        total_in_pending = Decimal(
            self.db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(
                Payment.receiver_wallet_id == wallet_id,
                Payment.status == PaymentStatus.PENDING,
            )
            .scalar() or 0
        )
        total_out_pending = Decimal(
            self.db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(
                Payment.sender_wallet_id == wallet_id,
                Payment.status == PaymentStatus.PENDING,
            )
            .scalar() or 0
        )

        balance = total_in_completed - total_out_completed

        return {
            "balance": balance,
            "total_in_completed": total_in_completed,
            "total_out_completed": total_out_completed,
            "total_in_pending": total_in_pending,
            "total_out_pending": total_out_pending,
        }

    def get_ledger(
        self, wallet_id: uuid.UUID, page: int, page_size: int
    ) -> tuple[List[LedgerEntry], int]:
        base_filter = [
            Payment.status == PaymentStatus.COMPLETED,
            or_(
                Payment.sender_wallet_id == wallet_id,
                Payment.receiver_wallet_id == wallet_id,
            ),
        ]

        total = self.db.execute(
            select(func.count()).select_from(Payment).where(*base_filter)
        ).scalar() or 0
        offset = (page - 1) * page_size

        rows = self.db.execute(
            select(
                Payment.id.label("id"),
                case(
                    (Payment.receiver_wallet_id == wallet_id, "IN"),
                    else_="OUT",
                ).label("direction"),
                Payment.amount.label("amount"),
                case(
                    (Payment.receiver_wallet_id == wallet_id, Payment.sender_wallet_id),
                    else_=Payment.receiver_wallet_id,
                ).label("counterparty_wallet_id"),
                Payment.created_at.label("occurred_at"),
                Payment.description.label("description"),
            )
            .where(*base_filter)
            .order_by(Payment.created_at.desc())
            .offset(offset)
            .limit(page_size)
        ).fetchall()

        entries = [
            LedgerEntry(
                id=row.id,
                source="payment",
                direction=row.direction,
                amount=Decimal(row.amount),
                counterparty_wallet_id=row.counterparty_wallet_id,
                occurred_at=row.occurred_at,
                description=row.description,
            )
            for row in rows
        ]

        return entries, total
