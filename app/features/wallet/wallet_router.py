import math
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.wallet.wallet_schemas import (
    WalletCreate,
    WalletFilters,
    WalletResponse,
    WalletSummaryResponse,
    WalletUpdate,
)
from app.features.wallet.wallet_service import WalletService

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.post("/", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(check_permissions(Permission.CREATE_WALLET))])
def create_wallet(data: WalletCreate, db: Session = Depends(get_db)):
    service = WalletService(db)
    obj = service.create(data)
    return success_response(data=WalletResponse.model_validate(obj).model_dump(),
                            messages=["wallet created"], status_code=201)


@router.get("/", dependencies=[Depends(check_permissions(Permission.VIEW_WALLETS))])
def get_wallets(filters: WalletFilters = Depends(), db: Session = Depends(get_db)):
    service = WalletService(db)
    items, total = service.get_list(filters=filters)
    pages = math.ceil(total / filters.size) if total else 0
    return success_response(data={
        "items": [WalletResponse.model_validate(i).model_dump() for i in items],
        "pagination": {"total": total, "page": filters.page, "size": filters.size, "pages": pages},
    })


@router.get("/{wallet_id}", dependencies=[Depends(check_permissions(Permission.VIEW_WALLET))])
def get_wallet(wallet_id: uuid.UUID, db: Session = Depends(get_db)):
    service = WalletService(db)
    obj = service.get_by_id(wallet_id)
    return success_response(data=WalletResponse.model_validate(obj).model_dump())


@router.put("/{wallet_id}", dependencies=[Depends(check_permissions(Permission.UPDATE_WALLET))])
def update_wallet(wallet_id: uuid.UUID, data: WalletUpdate, db: Session = Depends(get_db)):
    service = WalletService(db)
    obj = service.update(wallet_id, data)
    return success_response(data=WalletResponse.model_validate(obj).model_dump(),
                            messages=["wallet updated"])


@router.get("/{wallet_id}/summary",
            dependencies=[Depends(check_permissions(Permission.VIEW_WALLET))])
def get_wallet_summary(wallet_id: uuid.UUID, db: Session = Depends(get_db)):
    service = WalletService(db)
    service.get_by_id(wallet_id)  # raises 404 if not found
    summary = service.get_summary(wallet_id)
    return success_response(data=WalletSummaryResponse(**summary).model_dump())


@router.get("/{wallet_id}/ledger",
            dependencies=[Depends(check_permissions(Permission.VIEW_WALLET_LEDGER))])
def get_wallet_ledger(
    wallet_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = WalletService(db)
    service.get_by_id(wallet_id)  # raises 404 if not found
    entries, total = service.get_ledger(wallet_id, page=page, page_size=page_size)
    pages = math.ceil(total / page_size) if total else 0
    return success_response(data={
        "items": [e.model_dump() for e in entries],
        "pagination": {"total": total, "page": page, "size": page_size, "pages": pages},
    })
