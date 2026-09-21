# ============================================
# MEMBERSHIP ROUTER - API Endpoints
# ============================================

from fastapi import Depends
from sqlalchemy.orm import Session

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.auth.auth_dependencies import get_current_active_user
from app.features.users.users_models import User
from app.features.membership.membership_schemas import (
    MembershipCreate,
    MembershipFilters,
    MembershipListResponse,
    MembershipResponse,
    MembershipUpdate,
)
from app.features.membership.membership_service import MembershipService

router = create_crud_router(
    prefix="/membership",
    tag="membership",
    service_factory=lambda db: MembershipService(db),
    create_conf=CrudEndpointConfig(
        schema=MembershipCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_MEMBERSHIP))],
    ),
    update_conf=CrudEndpointConfig(
        schema=MembershipUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_MEMBERSHIP))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=MembershipResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_MEMBERSHIP))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=MembershipListResponse,
        filters=MembershipFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_MEMBERSHIPS))],
    ),
    scope_by_company=True,
)


@router.delete(
    "/{item_id}",
    dependencies=[Depends(check_permissions(Permission.DELETE_MEMBERSHIP))],
)
def delete_membership(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = MembershipService(db)
    service.enforce_company_scope(item_id, current_user)
    service.delete(item_id)
    return success_response(messages=["membership deleted"])
