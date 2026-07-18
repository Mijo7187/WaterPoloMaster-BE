import math

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.quarter_users.quarter_users_schemas import (
    QuarterUsersCreate,
    QuarterUsersFilters,
    QuarterUsersResponse,
)
from app.features.quarter_users.quarter_users_service import QuarterUsersService
from app.features.users.users_schemas import UserListResponse

router = APIRouter(prefix="/quarter-users", tags=["quarter-users"])


@router.get(
    "/users-not-in-quarter",
    dependencies=[Depends(check_permissions(Permission.VIEW_QUARTER_USERS))],
)
def get_users_not_in_quarter(
    quarter_id: int = Query(...),
    company_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = QuarterUsersService(db)
    users, total = service.get_users_not_in_quarter(quarter_id, company_id, page, size)
    pages = math.ceil(total / size) if total else 0
    return success_response(data={
        "items": [UserListResponse.model_validate(u).model_dump() for u in users],
        "pagination": {"total": total, "page": page, "size": size, "pages": pages},
    })


@router.get("/", dependencies=[Depends(check_permissions(Permission.VIEW_QUARTER_USERS))])
def get_quarter_users(filters: QuarterUsersFilters = Depends(), db: Session = Depends(get_db)):
    service = QuarterUsersService(db)
    items, total = service.get_list_with_payment_status(filters)
    pages = math.ceil(total / filters.size) if total else 0
    data_items = []
    for row, payment_status in items:
        resp = QuarterUsersResponse.model_validate(row)
        resp.payment_status = payment_status
        data_items.append(resp.model_dump())
    return success_response(data={
        "items": data_items,
        "pagination": {"total": total, "page": filters.page, "size": filters.size, "pages": pages},
    })


@router.get("/{item_id}", dependencies=[Depends(check_permissions(Permission.VIEW_QUARTER_USER))])
def get_quarter_user(item_id: int, db: Session = Depends(get_db)):
    service = QuarterUsersService(db)
    obj = service.get_by_id(item_id)
    return success_response(data=QuarterUsersResponse.model_validate(obj).model_dump())


@router.post("/", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(check_permissions(Permission.CREATE_QUARTER_USER))])
def add_quarter_user(data: QuarterUsersCreate, db: Session = Depends(get_db)):
    service = QuarterUsersService(db)
    obj = service.create(data)
    return success_response(
        data=QuarterUsersResponse.model_validate(obj).model_dump(),
        messages=["User added to quarter"],
        status_code=201,
    )


@router.delete("/{item_id}", dependencies=[Depends(check_permissions(Permission.DELETE_QUARTER_USER))])
def remove_quarter_user(item_id: int, db: Session = Depends(get_db)):
    QuarterUsersService(db).delete(item_id)
    return success_response(messages=["User removed from quarter"])
