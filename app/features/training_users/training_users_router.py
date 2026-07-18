import math

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.training_users.training_users_schemas import (
    TrainingUsersCreate,
    TrainingUsersFilters,
    TrainingUsersResponse,
)
from app.features.training_users.training_users_service import TrainingUsersService
from app.features.users.users_schemas import UserListResponse

router = APIRouter(prefix="/training-users", tags=["training-users"])


@router.get(
    "/users-not-in-training",
    dependencies=[Depends(check_permissions(Permission.VIEW_TRAINING_USERS))],
)
def get_users_not_in_training(
    training_id: int = Query(...),
    company_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = TrainingUsersService(db)
    users, total = service.get_users_not_in_training(training_id, company_id, page, size)
    pages = math.ceil(total / size) if total else 0
    return success_response(data={
        "items": [UserListResponse.model_validate(u).model_dump() for u in users],
        "pagination": {"total": total, "page": page, "size": size, "pages": pages},
    })


@router.get("/", dependencies=[Depends(check_permissions(Permission.VIEW_TRAINING_USERS))])
def get_training_users(filters: TrainingUsersFilters = Depends(), db: Session = Depends(get_db)):
    service = TrainingUsersService(db)
    items, total = service.get_list(filters=filters)
    pages = math.ceil(total / filters.size) if total else 0
    return success_response(data={
        "items": [TrainingUsersResponse.model_validate(i).model_dump() for i in items],
        "pagination": {"total": total, "page": filters.page, "size": filters.size, "pages": pages},
    })


@router.get("/{item_id}", dependencies=[Depends(check_permissions(Permission.VIEW_TRAINING_USERS_ITEM))])
def get_training_user(item_id: int, db: Session = Depends(get_db)):
    service = TrainingUsersService(db)
    obj = service.get_by_id(item_id)
    return success_response(data=TrainingUsersResponse.model_validate(obj).model_dump())


@router.post("/", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(check_permissions(Permission.CREATE_TRAINING_USERS))])
def add_training_user(data: TrainingUsersCreate, db: Session = Depends(get_db)):
    service = TrainingUsersService(db)
    obj = service.create(data)
    return success_response(
        data=TrainingUsersResponse.model_validate(obj).model_dump(),
        messages=["User added to training"],
        status_code=201,
    )


@router.delete("/{item_id}", dependencies=[Depends(check_permissions(Permission.DELETE_TRAINING_USERS))])
def remove_training_user(item_id: int, db: Session = Depends(get_db)):
    TrainingUsersService(db).delete(item_id)
    return success_response(messages=["User removed from training"])
