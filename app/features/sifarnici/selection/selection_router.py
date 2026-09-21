# ============================================
# SELECTION ROUTER - API Endpoints
# ============================================

from fastapi import Depends

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.permissions import Permission, check_permissions
from app.features.sifarnici.selection.selection_schemas import (
    SelectionCreate,
    SelectionFilters,
    SelectionListResponse,
    SelectionResponse,
    SelectionUpdate,
)
from app.features.sifarnici.selection.selection_service import SelectionService

router = create_crud_router(
    prefix="/selection",
    tag="selection",
    service_factory=lambda db: SelectionService(db),
    create_conf=CrudEndpointConfig(
        schema=SelectionCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_SELECTION))],
    ),
    update_conf=CrudEndpointConfig(
        schema=SelectionUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_SELECTION))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=SelectionResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_SELECTION))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=SelectionListResponse,
        filters=SelectionFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_SELECTIONS))],
    ),
    enable_soft_delete=True,
    deactivate_dependencies=[Depends(check_permissions(Permission.DELETE_SELECTION))],
    scope_by_company=True,
)
