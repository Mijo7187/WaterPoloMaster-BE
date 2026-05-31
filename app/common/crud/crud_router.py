# ============================================
# CRUD - Generic Router Factory
# ============================================
# Builds a FastAPI APIRouter with standard CRUD
# endpoints: POST, GET list, GET by id, PUT,
# and optionally POST deactivate (soft delete).
#
# Supports per-endpoint dependencies (permissions),
# query-parameter filters, and eager relation loading.
#
# USAGE:
#   router = create_crud_router(
#       prefix="/company",
#       tag="company",
#       service_factory=lambda db: CompanyService(db),
#       create_conf=CrudEndpointConfig(schema=CompanyCreate, dependencies=[...]),
#       update_conf=CrudEndpointConfig(schema=CompanyUpdate, dependencies=[...]),
#       response_conf=CrudEndpointConfig(schema=CompanyResponse, load_relations=[...]),
#       enable_soft_delete=True,
#       deactivate_dependencies=[Depends(check_permissions(Permission.DELETE_COMPANY))],
#   )
#   # You can add custom endpoints to the returned router:
#   @router.post("/{item_id}/custom")
#   def custom_endpoint(...): ...
# ============================================

import math
from typing import Callable, List, Any, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudEndpointConfig, CrudFilters,CrudListEndpointConfig
from app.core.db.database import get_db
from app.core.api.responses import success_response
from app.common.crud.crud_service import CrudService


def create_crud_router(
    prefix: str,
    tag: str,
    service_factory: Callable[[Session], Any],
    create_conf: CrudEndpointConfig,
    update_conf: CrudEndpointConfig,
    get_by_id_conf: CrudEndpointConfig,
    get_list_conf: CrudListEndpointConfig,
    enable_soft_delete: bool = False,
    deactivate_dependencies: List[Any] = [],
) -> APIRouter:
    """
    Build and return an APIRouter with standard CRUD endpoints.
 
    Args:
        prefix:                  URL prefix, e.g. "/company"
        tag:                     OpenAPI tag for grouping in docs
        service_factory:         Callable that receives a db Session and returns a service instance
        create_conf:             Config for POST / (schema, dependencies)
        update_conf:             Config for PUT /{id} (schema, dependencies)
        get_by_id_conf:          Config for GET /{id} (schema, dependencies)
        get_list_conf:           Config for GET / (schema, filters, dependencies)
        enable_soft_delete:      Whether to generate POST /{id}/deactivate
        deactivate_dependencies: Dependencies for the deactivate endpoint
 
    Notes:
        - load_relations is now defined in the repository (default_relations method)
        - Filters use field__operator convention (e.g. name__ilike, created_at__gte)
        - Pagination uses page/size params (defined in CrudFilters base class)
        - GET list always returns { items, total, page, size, pages }
    """
 
    # Lazy import to avoid circular dependency between common/ and features/
    from app.features.auth.auth_dependencies import get_current_active_user
    from app.features.users.users_models import User

    router = APIRouter(prefix=prefix, tags=[tag])
 
    # ── POST / ──────────────────────────────────────
 
    @router.post(
        "/",
        status_code=status.HTTP_201_CREATED,
        dependencies=create_conf.dependencies or [],
    )
    def create(
        data: create_conf.schema,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
    ):
        service = service_factory(db)
        obj = service.create(data, current_user=current_user)
        return success_response(
            data={obj.id},
            messages=[f"{tag} created"],
            status_code=201,
        )
 
    # ── GET / ───────────────────────────────────────
 
    filter_schema = get_list_conf.filters or CrudFilters
 
    @router.get(
        "/",
        dependencies=get_list_conf.dependencies or [],
    )
    def get_list(
        filters: filter_schema = Depends(),
        db: Session = Depends(get_db),
    ):
        service = service_factory(db)
        items, total = service.get_list(filters=filters)
        pages = math.ceil(total / filters.size) if total else 0
 
        return success_response(
            data={
                "items": [get_list_conf.schema.model_validate(i).model_dump() for i in items],
                "pagination": {
                    "total": total,
                    "page": filters.page,
                    "size": filters.size,
                    "pages": pages,
                },
            }
        )
 
    # ── GET /{id} ───────────────────────────────────
 
    @router.get(
        "/{item_id}",
        dependencies=get_by_id_conf.dependencies or [],
    )
    def get_by_id(
        item_id: int,
        db: Session = Depends(get_db),
    ):
        service = service_factory(db)
        obj = service.get_by_id(item_id)
        return success_response(
            data=get_by_id_conf.schema.model_validate(obj).model_dump(),
        )
 
    # ── PUT /{id} ───────────────────────────────────
 
    @router.put(
        "/{item_id}",
        dependencies=update_conf.dependencies or [],
    )
    def update(
        item_id: int,
        data: update_conf.schema,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
    ):
        service = service_factory(db)
        obj = service.update(item_id, data, current_user=current_user)
        return success_response(
            data=get_by_id_conf.schema.model_validate(obj).model_dump(),
            messages=[f"{tag} updated"],
        )
 
    # ── POST /{id}/deactivate (soft delete) ─────────
 
    if enable_soft_delete:
        @router.post(
            "/{item_id}/deactivate",
            dependencies=deactivate_dependencies or [],
        )
        def deactivate(
            item_id: int,
            db: Session = Depends(get_db),
        ):
            service = service_factory(db)
            obj = service.soft_delete(item_id)
            return success_response(
                data=get_by_id_conf.schema.model_validate(obj).model_dump(),
                messages=[f"{tag} deactivated"],
            )
 
    return router