import math

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.api.responses import success_response
from app.core.db.database import get_db
from app.core.permissions import Permission, check_permissions
from app.features.tournament_users.tournament_users_schemas import (
    TournamentUsersCreate,
    TournamentUsersFilters,
    TournamentUsersResponse,
)
from app.features.tournament_users.tournament_users_service import TournamentUsersService
from app.features.users.users_schemas import UserListResponse

router = APIRouter(prefix="/tournament-users", tags=["tournament-users"])


@router.get(
    "/users-not-in-tournament",
    dependencies=[Depends(check_permissions(Permission.VIEW_TOURNAMENT_USERS))],
)
def get_users_not_in_tournament(
    tournament_id: int = Query(...),
    company_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = TournamentUsersService(db)
    users, total = service.get_users_not_in_tournament(tournament_id, company_id, page, size)
    pages = math.ceil(total / size) if total else 0
    return success_response(data={
        "items": [UserListResponse.model_validate(u).model_dump() for u in users],
        "pagination": {"total": total, "page": page, "size": size, "pages": pages},
    })


@router.get("/", dependencies=[Depends(check_permissions(Permission.VIEW_TOURNAMENT_USERS))])
def get_tournament_users(filters: TournamentUsersFilters = Depends(), db: Session = Depends(get_db)):
    service = TournamentUsersService(db)
    items, total = service.get_list_with_payment_status(filters)
    pages = math.ceil(total / filters.size) if total else 0
    data_items = []
    for row, payment_status in items:
        resp = TournamentUsersResponse.model_validate(row)
        resp.payment_status = payment_status
        data_items.append(resp.model_dump())
    return success_response(data={
        "items": data_items,
        "pagination": {"total": total, "page": filters.page, "size": filters.size, "pages": pages},
    })


@router.get("/{item_id}", dependencies=[Depends(check_permissions(Permission.VIEW_TOURNAMENT_USER))])
def get_tournament_user(item_id: int, db: Session = Depends(get_db)):
    service = TournamentUsersService(db)
    obj = service.get_by_id(item_id)
    return success_response(data=TournamentUsersResponse.model_validate(obj).model_dump())


@router.post("/", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(check_permissions(Permission.CREATE_TOURNAMENT_USER))])
def add_tournament_user(data: TournamentUsersCreate, db: Session = Depends(get_db)):
    service = TournamentUsersService(db)
    obj = service.create(data)
    return success_response(
        data=TournamentUsersResponse.model_validate(obj).model_dump(),
        messages=["User added to tournament"],
        status_code=201,
    )


@router.delete("/{item_id}", dependencies=[Depends(check_permissions(Permission.DELETE_TOURNAMENT_USER))])
def remove_tournament_user(item_id: int, db: Session = Depends(get_db)):
    TournamentUsersService(db).delete(item_id)
    return success_response(messages=["User removed from tournament"])
