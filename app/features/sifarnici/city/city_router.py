# ============================================
# CITY ROUTER - API Endpoints
# ============================================
# Uses the generic sifarnik router factory.
# All CRUD endpoints are generated automatically.
# ============================================

from fastapi import Depends

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.permissions import Permission, check_permissions
from app.features.sifarnici.city.city_schemas import CityCreate, CityFilters, CityListResponse, CityUpdate, CityResponse
from app.features.sifarnici.city.city_service import CityService

router = create_crud_router(
    prefix="/city",
    tag="city",
    service_factory=lambda db: CityService(db),
    create_conf=CrudEndpointConfig(
        schema=CityCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_CITY))],
    ),
    update_conf=CrudEndpointConfig(
        schema=CityUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_CITY))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=CityResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_CITY))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=CityListResponse,
        filters=CityFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_CITIES))],
    ),
)
