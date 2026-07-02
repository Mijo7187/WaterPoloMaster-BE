# ============================================
# SWIMMING DISCIPLINE ROUTER - API Endpoints
# ============================================
# Uses the generic sifarnik router factory.
# All CRUD endpoints are generated automatically.
# ============================================

from fastapi import Depends

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.permissions import Permission, check_permissions
from app.features.sifarnici.swimming_discipline.swimming_discipline_schemas import (
    SwimmingDisciplineCreate,
    SwimmingDisciplineFilters,
    SwimmingDisciplineListResponse,
    SwimmingDisciplineUpdate,
    SwimmingDisciplineResponse,
)
from app.features.sifarnici.swimming_discipline.swimming_discipline_service import SwimmingDisciplineService

router = create_crud_router(
    prefix="/swimming-discipline",
    tag="swimming-discipline",
    service_factory=lambda db: SwimmingDisciplineService(db),
    create_conf=CrudEndpointConfig(
        schema=SwimmingDisciplineCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_SWIMMING_DISCIPLINE))],
    ),
    update_conf=CrudEndpointConfig(
        schema=SwimmingDisciplineUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_SWIMMING_DISCIPLINE))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=SwimmingDisciplineResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_SWIMMING_DISCIPLINE))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=SwimmingDisciplineListResponse,
        filters=SwimmingDisciplineFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_SWIMMING_DISCIPLINES))],
    ),
)
