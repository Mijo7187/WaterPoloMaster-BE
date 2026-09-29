# ============================================
# PAYMENT ROUTER - API Endpoints
# ============================================
# Generic CRUD factory. Payment ids are UUIDs (id_type), create returns the
# full payment (response_schema), and the list always carries a summary —
# from the ?wallet_id= wallet, the ADMIN's company, or (SUPER_ADMIN) the
# clubs' side of the whole app. No soft delete.
# ============================================

import uuid

from fastapi import Depends

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.permissions import Permission, check_permissions
from app.features.payment.payment_schemas import (
    PaymentCreate,
    PaymentFilters,
    PaymentResponse,
    PaymentSummary,
    PaymentUpdate,
)
from app.features.payment.payment_service import PaymentService

router = create_crud_router(
    prefix="/payment",
    tag="payment",
    service_factory=lambda db: PaymentService(db),
    create_conf=CrudEndpointConfig(
        schema=PaymentCreate,
        response_schema=PaymentResponse,
        dependencies=[Depends(check_permissions(Permission.CREATE_PAYMENT))],
    ),
    update_conf=CrudEndpointConfig(
        schema=PaymentUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_PAYMENT))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=PaymentResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_PAYMENT))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=PaymentResponse,
        filters=PaymentFilters,
        summary_schema=PaymentSummary,
        dependencies=[Depends(check_permissions(Permission.VIEW_PAYMENTS))],
    ),
    scope_by_company=True,
    id_type=uuid.UUID,
)
