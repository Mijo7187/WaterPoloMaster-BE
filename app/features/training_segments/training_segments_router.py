# ============================================
# TRAINING SEGMENT ROUTER - API Endpoints
# ============================================
# Manual router (segments need nested/discriminated writes the generic CRUD
# factory can't express). Modeled on training_users_router. The nested read of
# a full training timeline lives on GET /training/{id}; here we expose the
# per-segment write surface plus a single-segment GET.
# ============================================

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.auth.auth_dependencies import get_current_active_user
from app.features.training_segments.training_segments_schemas import (
    TrainingSegmentCreate,
    TrainingSegmentResponse,
    TrainingSegmentUpdate,
)
from app.features.training_segments.training_segments_service import TrainingSegmentService
from app.features.users.users_models import User

router = APIRouter(prefix="/training-segment", tags=["training-segments"])


@router.get(
    "/by-training/{training_id}",
    dependencies=[Depends(check_permissions(Permission.VIEW_TRAINING_SEGMENT))],
)
def list_segments_by_training(training_id: int, db: Session = Depends(get_db)):
    service = TrainingSegmentService(db)
    segments = service.list_by_training(training_id)
    return success_response(
        data=[TrainingSegmentResponse.model_validate(s).model_dump() for s in segments]
    )


@router.get(
    "/{item_id}",
    dependencies=[Depends(check_permissions(Permission.VIEW_TRAINING_SEGMENT))],
)
def get_training_segment(item_id: int, db: Session = Depends(get_db)):
    service = TrainingSegmentService(db)
    obj = service.get_by_id(item_id)
    return success_response(data=TrainingSegmentResponse.model_validate(obj).model_dump())


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_permissions(Permission.CREATE_TRAINING_SEGMENT))],
)
def create_training_segment(
    data: TrainingSegmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = TrainingSegmentService(db)
    obj = service.create(data, current_user=current_user)
    return success_response(
        data=TrainingSegmentResponse.model_validate(obj).model_dump(),
        messages=["Training segment created"],
        status_code=201,
    )


@router.patch(
    "/{item_id}",
    dependencies=[Depends(check_permissions(Permission.UPDATE_TRAINING_SEGMENT))],
)
def update_training_segment(
    item_id: int,
    data: TrainingSegmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = TrainingSegmentService(db)
    obj = service.update(item_id, data, current_user=current_user)
    return success_response(
        data=TrainingSegmentResponse.model_validate(obj).model_dump(),
        messages=["Training segment updated"],
    )


@router.delete(
    "/{item_id}",
    dependencies=[Depends(check_permissions(Permission.DELETE_TRAINING_SEGMENT))],
)
def delete_training_segment(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = TrainingSegmentService(db)
    service.delete(item_id, current_user=current_user)
    return success_response(messages=["Training segment deleted"])
