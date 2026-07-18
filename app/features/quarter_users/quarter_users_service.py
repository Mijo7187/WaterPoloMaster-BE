from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudCreateSchema
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.features.payment.payment_model import PaymentTypeCode
from app.features.payment.payment_repository import PaymentRepository
from app.features.payment.payment_schemas import PaymentCreate
from app.features.payment.payment_service import PaymentService
from app.features.quarter.quarter_repository import QuarterRepository
from app.features.quarter_users.quarter_users_model import QuarterUsers, TypeOfTraining
from app.features.quarter_users.quarter_users_repository import QuarterUsersRepository
from app.features.wallet.wallet_model import WalletOwnerType
from app.features.wallet.wallet_repository import WalletRepository


class QuarterUsersService(CrudService[QuarterUsers]):
    def __init__(self, db: Session):
        super().__init__(db, QuarterUsersRepository(db))

    def create(self, data: CrudCreateSchema, **kwargs):
        existing = (
            self.db.query(QuarterUsers)
            .filter(
                QuarterUsers.quarter_id == data.quarter_id,
                QuarterUsers.user_id == data.user_id,
            )
            .first()
        )
        if existing:
            raise ConflictException("User is already registered for this quarter")

        # Resolve everything the fee payment needs BEFORE inserting the membership,
        # so a bad request fails without leaving a member without a payment.
        quarter = QuarterRepository(self.db).get_by_id(data.quarter_id)
        if not quarter:
            raise NotFoundException("Quarter not found")

        training_type = getattr(data.type_of_training, "value", data.type_of_training)
        if training_type == TypeOfTraining.WATERPOLO.value:
            price = quarter.waterpolo_price
        else:
            price = quarter.swimming_price
        if price is None or price <= 0:
            raise BadRequestException("Quarter has no price set for this training type")

        wallet_repo = WalletRepository(self.db)
        sender_wallet = wallet_repo.get_by_owner(data.user_id, WalletOwnerType.USER)
        if not sender_wallet:
            raise NotFoundException("User wallet not found")
        receiver_wallet = wallet_repo.get_by_owner(
            quarter.company_id, WalletOwnerType.COMPANY
        )
        if not receiver_wallet:
            raise NotFoundException("Club wallet not found")

        if hasattr(data.type_of_training, "value"):
            data.type_of_training = data.type_of_training.value
        obj = super().create(data, **kwargs)

        PaymentService(self.db).create(
            PaymentCreate(
                sender_wallet_id=sender_wallet.id,
                receiver_wallet_id=receiver_wallet.id,
                payment_type=PaymentTypeCode.USER_QUARTERLY_FEE,
                amount=price,
                quarter_id=data.quarter_id,
            )
        )
        return obj

    def delete(self, obj_id: int) -> None:
        obj = self.db.get(QuarterUsers, obj_id)
        if not obj:
            raise NotFoundException("Quarter user entry not found")

        sender_wallet = WalletRepository(self.db).get_by_owner(
            obj.user_id, WalletOwnerType.USER
        )
        if sender_wallet:
            PaymentRepository(self.db).delete_pending_quarterly_fee(
                sender_wallet.id, obj.quarter_id
            )

        self.db.delete(obj)
        self.db.commit()

    def get_list_with_payment_status(self, filters):
        return self.repository.get_list_with_payment_status(filters)

    def get_users_not_in_quarter(self, quarter_id: int, company_id: int, page: int = 1, size: int = 20):
        return self.repository.get_users_not_in_quarter(quarter_id, company_id, page, size)
