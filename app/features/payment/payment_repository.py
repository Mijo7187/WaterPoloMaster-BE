from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.payment.payment_model import Payment


class PaymentRepository(CrudRepository[Payment]):
    def __init__(self, db: Session):
        super().__init__(db, Payment)

    def get_list_relations(self):
        return [
            lambda: selectinload(Payment.sender_wallet),
            lambda: selectinload(Payment.receiver_wallet),
            lambda: selectinload(Payment.payment_type),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Payment.sender_wallet),
            lambda: selectinload(Payment.receiver_wallet),
            lambda: selectinload(Payment.payment_type),
        ]
