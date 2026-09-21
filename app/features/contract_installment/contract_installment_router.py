# ============================================
# CONTRACT INSTALLMENT ROUTER - API Endpoints
# ============================================
# Generic CRUD factory, plus a waive endpoint and a
# custom DELETE.
#
# Installments are normally written with the contract
# (MEMBERSHIP installments_list) or by the monthly salary job
# (STAFF). These endpoints edit ONE row at a time; a MEMBERSHIP
# contract's amount / dates / status re-sync after every change.
# Reads are scoped to the caller's company through the contract.
# ============================================

from fastapi import Depends
from sqlalchemy.orm import Session

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.auth.auth_dependencies import get_current_active_user
from app.features.contract_installment.contract_installment_schemas import (
    ContractInstallmentCreate,
    ContractInstallmentFilters,
    ContractInstallmentResponse,
    ContractInstallmentUpdate,
)
from app.features.contract_installment.contract_installment_service import (
    ContractInstallmentService,
)
from app.features.users.users_models import User

router = create_crud_router(
    prefix="/contract-installment",
    tag="contract-installment",
    service_factory=lambda db: ContractInstallmentService(db),
    create_conf=CrudEndpointConfig(
        schema=ContractInstallmentCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_CONTRACT_INSTALLMENT))],
    ),
    update_conf=CrudEndpointConfig(
        schema=ContractInstallmentUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_CONTRACT_INSTALLMENT))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=ContractInstallmentResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_CONTRACT_INSTALLMENT))],
    ),
    get_list_conf=CrudListEndpointConfig(
        # ContractInstallmentResponse, not the List one: the service attaches
        # paid_amount / payment_status to every row in get_list, and the lean
        # schema would drop them on the way out.
        schema=ContractInstallmentResponse,
        filters=ContractInstallmentFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_CONTRACT_INSTALLMENTS))],
    ),
    scope_by_company=True,
)


@router.post(
    "/{item_id}/waive",
    dependencies=[Depends(check_permissions(Permission.UPDATE_CONTRACT_INSTALLMENT))],
)
def waive_installment(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Forgive one period. Drops any PENDING payment already raised for it."""
    obj = ContractInstallmentService(db).waive(item_id, current_user=current_user)
    return success_response(
        data=ContractInstallmentResponse.model_validate(obj).model_dump(),
        messages=["installment waived"],
    )


@router.delete(
    "/{item_id}",
    dependencies=[Depends(check_permissions(Permission.DELETE_CONTRACT_INSTALLMENT))],
)
def delete_contract_installment(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ContractInstallmentService(db)
    service.enforce_company_scope(item_id, current_user)
    service.delete(item_id)
    return success_response(messages=["contract installment deleted"])
