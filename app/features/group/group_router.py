import math

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.auth.auth_dependencies import get_current_active_user
from app.features.group.group_schemas import (
    GroupCreate,
    GroupFilters,
    GroupResponse,
)
from app.features.group.group_service import GroupService
from app.features.users.users_models import User

router = APIRouter(prefix="/group", tags=["group"])


@router.get("/", dependencies=[Depends(check_permissions(Permission.VIEW_GROUPS))])
def get_groups(
    filters: GroupFilters = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = GroupService(db)
    items, total = service.get_list(filters=filters, company_id=service.company_scope_for(current_user))
    pages = math.ceil(total / filters.size) if total else 0
    return success_response(data={
        "items": [GroupResponse.model_validate(i).model_dump() for i in items],
        "pagination": {"total": total, "page": filters.page, "size": filters.size, "pages": pages},
    })


@router.get("/{item_id}", dependencies=[Depends(check_permissions(Permission.VIEW_GROUP))])
def get_group(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = GroupService(db)
    service.enforce_company_read(item_id, current_user)
    obj = service.get_by_id(item_id)
    return success_response(data=GroupResponse.model_validate(obj).model_dump())


@router.post("/", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(check_permissions(Permission.CREATE_GROUP))])
def add_group(
    data: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = GroupService(db)
    obj = service.create(data, current_user=current_user)
    # Re-read so the nested season / selection are eager-loaded.
    obj = service.get_by_id(obj.id)
    return success_response(
        data=GroupResponse.model_validate(obj).model_dump(),
        messages=["Group created"],
        status_code=201,
    )


@router.delete("/{item_id}",
               dependencies=[Depends(check_permissions(Permission.DELETE_GROUP))])
def remove_group(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = GroupService(db)
    service.enforce_company_scope(item_id, current_user)
    service.delete(item_id)
    return success_response(messages=["Group deleted"])
