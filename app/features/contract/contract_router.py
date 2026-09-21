# ============================================
# CONTRACT ROUTER - API Endpoints
# ============================================
# Generic CRUD factory, plus a custom DELETE and the
# activation endpoint that generates installments.
# ============================================

from fastapi import Depends
from sqlalchemy.orm import Session

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.auth.auth_dependencies import get_current_active_user
from app.features.contract.contract_schemas import (
    ContractCreate,
    ContractFilters,
    ContractListResponse,
    ContractResponse,
    ContractUpdate,
)
from app.features.contract.contract_service import ContractService
from app.features.users.users_models import User

router = create_crud_router(
    prefix="/contract",
    tag="contract",
    service_factory=lambda db: ContractService(db),
    create_conf=CrudEndpointConfig(
        schema=ContractCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_CONTRACT))],
    ),
    update_conf=CrudEndpointConfig(
        schema=ContractUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_CONTRACT))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=ContractResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_CONTRACT))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=ContractListResponse,
        filters=ContractFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_CONTRACTS))],
    ),
    scope_by_company=True,
)


@router.post(
    "/{item_id}/activate",
    dependencies=[Depends(check_permissions(Permission.UPDATE_CONTRACT))],
)
def activate_contract(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Manual status refresh: recompute the status from the dates now.

    Status is already computed on every save and moved daily by the status
    job, so the frontend does not need to call this after create/update. It
    never generates MEMBERSHIP installments; CANCELLED stays CANCELLED.
    """
    service = ContractService(db)
    service.enforce_company_scope(item_id, current_user)
    obj = service.activate(item_id, current_user=current_user)
    return success_response(
        data=ContractResponse.model_validate(obj).model_dump(),
        messages=["contract status refreshed"],
    )


@router.delete(
    "/{item_id}",
    dependencies=[Depends(check_permissions(Permission.DELETE_CONTRACT))],
)
def delete_contract(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ContractService(db)
    service.enforce_company_scope(item_id, current_user)
    service.delete(item_id)
    return success_response(messages=["contract deleted"])
