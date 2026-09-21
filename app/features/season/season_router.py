# ============================================
# SEASON ROUTER - API Endpoints
# ============================================
# Uses the generic CRUD router factory for
# create / update / get / list, plus a custom
# DELETE endpoint (the factory only ships a
# soft-delete, and season has no is_active).
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
from app.features.season.season_schemas import (
    SeasonCreate,
    SeasonFilters,
    SeasonListResponse,
    SeasonResponse,
    SeasonUpdate,
)
from app.features.season.season_service import SeasonService

router = create_crud_router(
    prefix="/season",
    tag="season",
    service_factory=lambda db: SeasonService(db),
    create_conf=CrudEndpointConfig(
        schema=SeasonCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_SEASON))],
    ),
    update_conf=CrudEndpointConfig(
        schema=SeasonUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_SEASON))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=SeasonResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_SEASON))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=SeasonListResponse,
        filters=SeasonFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_SEASONS))],
    ),
    scope_by_company=True,
)


@router.delete(
    "/{item_id}",
    dependencies=[Depends(check_permissions(Permission.DELETE_SEASON))],
)
def delete_season(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = SeasonService(db)
    service.enforce_company_scope(item_id, current_user)
    service.delete(item_id)
    return success_response(messages=["season deleted"])
