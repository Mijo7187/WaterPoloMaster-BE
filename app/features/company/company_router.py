from fastapi import Depends

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.permissions import Permission, check_permissions
from .company_schemas import CompanyCreate, CompanyFilters, CompanyResponse, CompanyUpdate,CompanyListResponse
from .company_service import CompanyService

router = create_crud_router(
    prefix="/company",
    tag="company",
    service_factory=lambda db: CompanyService(db),
    create_conf=CrudEndpointConfig(
        schema=CompanyCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_COMPANY))],
    ),
    update_conf=CrudEndpointConfig(
        schema=CompanyUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_COMPANY))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=CompanyResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_COMPANY))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=CompanyListResponse,
        filters=CompanyFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_COMPANIES))],
    ),
    enable_soft_delete=True,
    deactivate_dependencies=[Depends(check_permissions(Permission.UPDATE_COMPANY))],
)
