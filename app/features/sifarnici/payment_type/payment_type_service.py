from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.features.sifarnici.payment_type.payment_type_model import PaymentType
from app.features.sifarnici.payment_type.payment_type_repository import PaymentTypeRepository


class PaymentTypeService(CrudService[PaymentType]):
    def __init__(self, db: Session):
        super().__init__(db, PaymentTypeRepository(db))
