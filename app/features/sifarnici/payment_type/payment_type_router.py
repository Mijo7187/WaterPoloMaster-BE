import math

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.sifarnici.payment_type.payment_type_schemas import (
    PaymentTypeFilters,
    PaymentTypeListResponse,
    PaymentTypeResponse,
)
from app.features.sifarnici.payment_type.payment_type_service import PaymentTypeService

router = APIRouter(prefix="/payment-type", tags=["payment-type"])


@router.get("/", dependencies=[Depends(check_permissions(Permission.VIEW_PAYMENT_TYPES))])
def get_payment_types(filters: PaymentTypeFilters = Depends(), db: Session = Depends(get_db)):
    service = PaymentTypeService(db)
    items, total = service.get_list(filters=filters)
    pages = math.ceil(total / filters.size) if total else 0
    return success_response(data={
        "items": [PaymentTypeListResponse.model_validate(i).model_dump() for i in items],
        "pagination": {"total": total, "page": filters.page, "size": filters.size, "pages": pages},
    })


@router.get("/{item_id}", dependencies=[Depends(check_permissions(Permission.VIEW_PAYMENT_TYPE))])
def get_payment_type(item_id: int, db: Session = Depends(get_db)):
    service = PaymentTypeService(db)
    obj = service.get_by_id(item_id)
    return success_response(data=PaymentTypeResponse.model_validate(obj).model_dump())
