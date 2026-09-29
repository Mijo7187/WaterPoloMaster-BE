import math

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.auth.auth_dependencies import get_current_active_user
from app.features.group_user.group_user_schemas import (
    GroupUserCreate,
    GroupUserFilters,
    GroupUserResponse,
)
from app.features.group_user.group_user_service import GroupUserService
from app.features.users.users_models import User

router = APIRouter(prefix="/group-user", tags=["group-user"])


@router.get("/", dependencies=[Depends(check_permissions(Permission.VIEW_GROUP_USERS))])
def get_group_users(
    filters: GroupUserFilters = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = GroupUserService(db)
    items, total = service.get_list(filters=filters, company_id=service.company_scope_for(current_user))
    pages = math.ceil(total / filters.size) if total else 0
    return success_response(data={
        "items": [GroupUserResponse.model_validate(i).model_dump() for i in items],
        "pagination": {"total": total, "page": filters.page, "size": filters.size, "pages": pages},
    })


@router.get("/{item_id}", dependencies=[Depends(check_permissions(Permission.VIEW_GROUP_USER))])
def get_group_user(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = GroupUserService(db)
    service.enforce_company_read(item_id, current_user)
    obj = service.get_by_id(item_id)
    return success_response(data=GroupUserResponse.model_validate(obj).model_dump())


@router.post("/", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(check_permissions(Permission.CREATE_GROUP_USER))])
def add_group_user(
    data: GroupUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = GroupUserService(db)
    obj = service.create(data, current_user=current_user)
    # Re-read so the nested group / user are eager-loaded.
    obj = service.get_by_id(obj.id)
    return success_response(
        data=GroupUserResponse.model_validate(obj).model_dump(),
        messages=["User added to group"],
        status_code=201,
    )


@router.delete("/{item_id}",
               dependencies=[Depends(check_permissions(Permission.DELETE_GROUP_USER))])
def remove_group_user(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = GroupUserService(db)
    service.enforce_company_scope(item_id, current_user)
    service.delete(item_id)
    return success_response(messages=["User removed from group"])
