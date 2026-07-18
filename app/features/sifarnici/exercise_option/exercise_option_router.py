# ============================================
# EXERCISE OPTION ROUTER - API Endpoints
# ============================================
# Uses the generic sifarnik router factory.
# ============================================

from fastapi import Depends

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.permissions import Permission, check_permissions
from app.features.sifarnici.exercise_option.exercise_option_schemas import (
    ExerciseOptionCreate,
    ExerciseOptionFilters,
    ExerciseOptionListResponse,
    ExerciseOptionUpdate,
    ExerciseOptionResponse,
)
from app.features.sifarnici.exercise_option.exercise_option_service import ExerciseOptionService

router = create_crud_router(
    prefix="/exercise-option",
    tag="exercise-option",
    service_factory=lambda db: ExerciseOptionService(db),
    create_conf=CrudEndpointConfig(
        schema=ExerciseOptionCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_EXERCISE_OPTION))],
    ),
    update_conf=CrudEndpointConfig(
        schema=ExerciseOptionUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_EXERCISE_OPTION))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=ExerciseOptionResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_EXERCISE_OPTION))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=ExerciseOptionListResponse,
        filters=ExerciseOptionFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_EXERCISE_OPTIONS))],
    ),
)
