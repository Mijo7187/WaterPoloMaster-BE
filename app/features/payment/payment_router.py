import math
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.payment.payment_schemas import (
    PaymentCreate,
    PaymentFilters,
    PaymentResponse,
    PaymentUpdate,
)
from app.features.payment.payment_service import PaymentService

router = APIRouter(tags=["payment"])


@router.post("/payment/", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(check_permissions(Permission.CREATE_PAYMENT))])
def create_payment(data: PaymentCreate, db: Session = Depends(get_db)):
    service = PaymentService(db)
    obj = service.create(data)
    return success_response(data=PaymentResponse.model_validate(obj).model_dump(),
                            messages=["payment created"], status_code=201)


@router.get("/payment/", dependencies=[Depends(check_permissions(Permission.VIEW_PAYMENTS))])
def get_payments(filters: PaymentFilters = Depends(), db: Session = Depends(get_db)):
    service = PaymentService(db)
    items, total = service.get_list(filters=filters)
    pages = math.ceil(total / filters.size) if total else 0
    return success_response(data={
        "items": [PaymentResponse.model_validate(i).model_dump() for i in items],
        "pagination": {"total": total, "page": filters.page, "size": filters.size, "pages": pages},
    })


@router.get("/payment/{payment_id}",
            dependencies=[Depends(check_permissions(Permission.VIEW_PAYMENT))])
def get_payment(payment_id: uuid.UUID, db: Session = Depends(get_db)):
    service = PaymentService(db)
    obj = service.get_by_id(payment_id)
    return success_response(data=PaymentResponse.model_validate(obj).model_dump())


@router.put("/payment/{payment_id}",
            dependencies=[Depends(check_permissions(Permission.UPDATE_PAYMENT))])
def update_payment(payment_id: uuid.UUID, data: PaymentUpdate, db: Session = Depends(get_db)):
    service = PaymentService(db)
    obj = service.update(payment_id, data)
    return success_response(data=PaymentResponse.model_validate(obj).model_dump(),
                            messages=["payment updated"])
