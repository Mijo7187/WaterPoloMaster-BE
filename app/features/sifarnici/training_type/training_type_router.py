# ============================================
# TRAINING TYPE ROUTER - API Endpoints
# ============================================
# Uses the generic sifarnik router factory.
# All CRUD endpoints are generated automatically.
# ============================================

from fastapi import Depends

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.permissions import Permission, check_permissions
from app.features.sifarnici.training_type.training_type_schemas import (
    TrainingTypeCreate,
    TrainingTypeFilters,
    TrainingTypeListResponse,
    TrainingTypeUpdate,
    TrainingTypeResponse,
)
from app.features.sifarnici.training_type.training_type_service import TrainingTypeService

router = create_crud_router(
    prefix="/training-type",
    tag="training-type",
    service_factory=lambda db: TrainingTypeService(db),
    create_conf=CrudEndpointConfig(
        schema=TrainingTypeCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_TRAINING_TYPE))],
    ),
    update_conf=CrudEndpointConfig(
        schema=TrainingTypeUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_TRAINING_TYPE))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=TrainingTypeResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_TRAINING_TYPE))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=TrainingTypeListResponse,
        filters=TrainingTypeFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_TRAINING_TYPES))],
    ),
)
