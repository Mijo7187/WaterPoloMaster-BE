from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.sifarnici.payment_type.payment_type_model import PaymentType


class PaymentTypeRepository(CrudRepository[PaymentType]):
    def __init__(self, db: Session):
        super().__init__(db, PaymentType)
