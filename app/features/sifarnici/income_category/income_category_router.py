import math
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.sifarnici.income_category.income_category_model import IncomeCategory
from app.features.sifarnici.income_category.income_category_schemas import (
    IncomeCategoryResponse,
)
from app.features.sifarnici.income_category.income_category_service import IncomeCategoryService

# TODO: per-wallet category CRUD

router = APIRouter(prefix="/income-category", tags=["income-category"])


@router.get("/", dependencies=[Depends(check_permissions(Permission.VIEW_INCOME_CATEGORIES))])
def get_income_categories(
    wallet_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Returns global categories (wallet_id IS NULL) plus the specified wallet's own categories."""
    q = db.query(IncomeCategory).filter(IncomeCategory.is_active.is_(True))
    if wallet_id:
        q = q.filter(
            (IncomeCategory.wallet_id.is_(None)) | (IncomeCategory.wallet_id == wallet_id)
        )
    else:
        q = q.filter(IncomeCategory.wallet_id.is_(None))

    total = q.count()
    items = q.order_by(IncomeCategory.id.asc()).offset((page - 1) * size).limit(size).all()
    pages = math.ceil(total / size) if total else 0
    return success_response(data={
        "items": [IncomeCategoryResponse.model_validate(i).model_dump() for i in items],
        "pagination": {"total": total, "page": page, "size": size, "pages": pages},
    })


@router.get("/{item_id}", dependencies=[Depends(check_permissions(Permission.VIEW_INCOME_CATEGORY))])
def get_income_category(item_id: int, db: Session = Depends(get_db)):
    service = IncomeCategoryService(db)
    obj = service.get_by_id(item_id)
    return success_response(data=IncomeCategoryResponse.model_validate(obj).model_dump())
