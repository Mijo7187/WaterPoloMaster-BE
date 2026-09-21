from fastapi import Depends, status
from sqlalchemy.orm import Session

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.api.exceptions import NotFoundException
from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.auth.auth_dependencies import get_current_active_user
from app.features.users.users_models import User
from app.features.users.users_schemas import (
    UserCreate,
    UserFilters,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.features.users.users_service import UserService

router = create_crud_router(
    prefix="/users",
    tag="users",
    service_factory=lambda db: UserService(db),
    create_conf=CrudEndpointConfig(schema=UserCreate),
    update_conf=CrudEndpointConfig(
        schema=UserUpdate,
        dependencies=[Depends(check_permissions(Permission.UPDATE_USER))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema=UserResponse,
        dependencies=[Depends(check_permissions(Permission.VIEW_USER))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema=UserListResponse,
        filters=UserFilters,
        dependencies=[Depends(check_permissions(Permission.VIEW_USERS))],
    ),
    enable_soft_delete=True,
    deactivate_dependencies=[Depends(check_permissions(Permission.DEACTIVATE_USER))],
    scope_by_company=True,
)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK,
               dependencies=[Depends(check_permissions(Permission.DELETE_USER))])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = UserService(db)
    service.enforce_company_scope(user_id, current_user)
    if not service.delete_user(user_id):
        raise NotFoundException("User not found")
    return success_response(messages=["User deleted"])
