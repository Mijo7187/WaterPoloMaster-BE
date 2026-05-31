# ============================================
# TRAINING ROUTER - API Endpoints
# ============================================
# Uses the generic CRUD router factory.
# All CRUD endpoints are generated automatically.
# ============================================

from fastapi import Depends

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.permissions import Permission, check_permissions
from app.features.training.training_schemas import TrainingCreate, TrainingFilters, TrainingListResponse, TrainingUpdate, TrainingResponse
from app.features.training.training_service import TrainingService

router = create_crud_router(
    prefix="/training",
    tag="training",
    service_factory=lambda db: TrainingService(db),
    create_conf=CrudEndpointConfig(
        schema=TrainingCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_TRAINING))],
    ),
    update_conf=CrudEndpointConfig(
        schema=TrainingUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_TRAINING))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=TrainingResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_TRAINING))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=TrainingListResponse,
        filters=TrainingFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_TRAININGS))],
    ),
)
