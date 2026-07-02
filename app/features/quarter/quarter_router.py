# ============================================
# QUARTER ROUTER - API Endpoints
# ============================================
# Uses the generic CRUD router factory for
# create / update / get / list, plus a custom
# DELETE endpoint (the factory only ships a
# soft-delete, and quarter has no is_active).
# ============================================

from fastapi import Depends
from sqlalchemy.orm import Session

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.quarter.quarter_schemas import (
    QuarterCreate,
    QuarterFilters,
    QuarterListResponse,
    QuarterResponse,
    QuarterUpdate,
)
from app.features.quarter.quarter_service import QuarterService

router = create_crud_router(
    prefix="/quarter",
    tag="quarter",
    service_factory=lambda db: QuarterService(db),
    create_conf=CrudEndpointConfig(
        schema=QuarterCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_QUARTER))],
    ),
    update_conf=CrudEndpointConfig(
        schema=QuarterUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_QUARTER))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=QuarterResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_QUARTER))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=QuarterListResponse,
        filters=QuarterFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_QUARTERS))],
    ),
)


@router.delete(
    "/{item_id}",
    dependencies=[Depends(check_permissions(Permission.DELETE_QUARTER))],
)
def delete_quarter(item_id: int, db: Session = Depends(get_db)):
    QuarterService(db).delete(item_id)
    return success_response(messages=["quarter deleted"])
