# ============================================
# TOURNAMENT ROUTER - API Endpoints
# ============================================
# Uses the generic CRUD router factory for
# create / update / get / list, plus a custom
# DELETE endpoint (the factory only ships a
# soft-delete, and tournament has no is_active).
# ============================================

from fastapi import Depends
from sqlalchemy.orm import Session

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.auth.auth_dependencies import get_current_active_user
from app.features.users.users_models import User
from app.features.tournament.tournament_schemas import (
    TournamentCreate,
    TournamentFilters,
    TournamentListResponse,
    TournamentResponse,
    TournamentUpdate,
)
from app.features.tournament.tournament_service import TournamentService

router = create_crud_router(
    prefix="/tournament",
    tag="tournament",
    service_factory=lambda db: TournamentService(db),
    create_conf=CrudEndpointConfig(
        schema=TournamentCreate,
        dependencies=[Depends(check_permissions(Permission.CREATE_TOURNAMENT))],
    ),
    update_conf=CrudEndpointConfig(
        schema=TournamentUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_TOURNAMENT))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=TournamentResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_TOURNAMENT))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=TournamentListResponse,
        filters=TournamentFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_TOURNAMENTS))],
    ),
    scope_by_company=True,
)


@router.delete(
    "/{item_id}",
    dependencies=[Depends(check_permissions(Permission.DELETE_TOURNAMENT))],
)
def delete_tournament(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = TournamentService(db)
    service.enforce_company_scope(item_id, current_user)
    service.delete(item_id)
    return success_response(messages=["tournament deleted"])
