import math

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from .company_schemas import (
    AcademyCompanyAttach,
    CompanyCreate,
    CompanyFilters,
    CompanyResponse,
    CompanyUpdate,
    CompanyListResponse,
)
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
    scope_by_company=True,
)


# ============================================
# ACADEMY MEMBERSHIP — SUPER_ADMIN only
# ============================================
# Lives on its own /academy prefix rather than under /company, because
# GET /company/{item_id} takes an int path param and would shadow
# /company/academy/... with a 422.
academy_router = APIRouter(prefix="/academy", tags=["academy"])


@academy_router.get(
    "/{academy_id}/companies",
    dependencies=[Depends(check_permissions(Permission.VIEW_ACADEMY_COMPANIES))],
)
def get_academy_companies(
    academy_id: int,
    filters: CompanyFilters = Depends(),
    db: Session = Depends(get_db),
):
    """Every company attached to this academy."""
    service = CompanyService(db)
    items, total = service.get_academy_members(academy_id, filters)
    pages = math.ceil(total / filters.size) if total else 0
    return success_response(
        data={
            "items": [CompanyListResponse.model_validate(i).model_dump() for i in items],
            "pagination": {
                "total": total,
                "page": filters.page,
                "size": filters.size,
                "pages": pages,
            },
        }
    )


@academy_router.post(
    "/{academy_id}/companies",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_permissions(Permission.CREATE_ACADEMY_COMPANY))],
)
def add_company_to_academy(
    academy_id: int,
    data: AcademyCompanyAttach,
    db: Session = Depends(get_db),
):
    service = CompanyService(db)
    obj = service.add_company_to_academy(academy_id, data.company_id)
    return success_response(
        data=CompanyResponse.model_validate(obj).model_dump(),
        messages=["company added to academy"],
        status_code=201,
    )


@academy_router.delete(
    "/{academy_id}/companies/{company_id}",
    dependencies=[Depends(check_permissions(Permission.DELETE_ACADEMY_COMPANY))],
)
def remove_company_from_academy(
    academy_id: int,
    company_id: int,
    db: Session = Depends(get_db),
):
    service = CompanyService(db)
    obj = service.remove_company_from_academy(academy_id, company_id)
    return success_response(
        data=CompanyResponse.model_validate(obj).model_dump(),
        messages=["company removed from academy"],
    )