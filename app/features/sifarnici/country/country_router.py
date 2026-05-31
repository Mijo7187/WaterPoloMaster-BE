# ============================================
# COUNTRY ROUTER - API Endpoints
# ============================================
# Uses the generic sifarnik router factory.
# All CRUD endpoints are generated automatically.
# ============================================

from fastapi import Depends

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.permissions import Permission, check_permissions
from app.features.sifarnici.country.country_schemas import CountryCreate, CountryFilters, CountryListResponse, CountryUpdate, CountryResponse
from app.features.sifarnici.country.country_service import CountryService

router = create_crud_router(
    prefix="/country",
    tag="country",
    service_factory=lambda db: CountryService(db),
     create_conf=CrudEndpointConfig(
        schema=CountryCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_COUNTRY))],
    ),
    update_conf=CrudEndpointConfig(
        schema=CountryUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_COUNTRY))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=CountryResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_COUNTRY))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=CountryListResponse,
        filters=CountryFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_COUNTRIES))],
    ),
  
)
