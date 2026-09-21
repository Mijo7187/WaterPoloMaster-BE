# ============================================
# MEMBERSHIP SERVICE - Business Logic
# ============================================

from typing import Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudHooks
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.features.membership.membership_model import Membership, divides_term_evenly
from app.features.membership.membership_repository import MembershipRepository
from app.features.users.users_models import User, UserRole


def _validate_installments(months_count, installments_count) -> None:
    """Reject a split that would give fractional-month installments."""
    if months_count is None or installments_count is None:
        return
    if not divides_term_evenly(months_count, installments_count):
        raise BadRequestException(
            f"installments_count must divide the {months_count}-month term "
            f"evenly — {installments_count} does not."
        )


def _assert_unique(db, company_id, name, program, exclude_id: Optional[int] = None) -> None:
    """Enforce UNIQUE(company_id, name, program) with a readable 409.

    Checked on update as well as create — leaving it to the DB constraint
    would surface a raw IntegrityError instead.
    """
    if company_id is None or name is None or program is None:
        return

    q = db.query(Membership).filter(
        Membership.company_id == company_id,
        Membership.name == name,
        Membership.program == program,
    )
    if exclude_id is not None:
        q = q.filter(Membership.id != exclude_id)

    if q.first():
        raise ConflictException(
            "This company already has a membership with that name and program."
        )


def _membership_pre_create(
    data: dict, db, current_user: Optional[User] = None
) -> dict:
    _validate_installments(data.get("months_count"), data.get("installments_count"))
    _assert_unique(db, data.get("company_id"), data.get("name"), data.get("program"))
    return data


def _membership_pre_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """
    Row-level authorization plus the same validation as create, merged against
    the existing row. See exercise_option_service for the canonical scoping form.
    """
    existing = db.query(Membership).filter(Membership.id == obj_id).first()

    if current_user is not None and UserRole.SUPER_ADMIN.value not in (
        current_user.roles or []
    ):
        if existing and existing.company_id != current_user.company_id:
            raise ForbiddenException(
                "You can only edit memberships in your own company."
            )

    if existing:
        _validate_installments(
            data.get("months_count", existing.months_count),
            data.get("installments_count", existing.installments_count),
        )
        _assert_unique(
            db,
            data.get("company_id", existing.company_id),
            data.get("name", existing.name),
            data.get("program", existing.program),
            exclude_id=obj_id,
        )

    return data


class MembershipService(CrudService[Membership]):
    def __init__(self, db: Session):
        super().__init__(
            db,
            MembershipRepository(db),
            hooks=CrudHooks(
                pre_create=_membership_pre_create,
                pre_update=_membership_pre_update,
            ),
        )

    def delete(self, obj_id: int) -> None:
        obj = self.db.get(Membership, obj_id)
        if not obj:
            raise NotFoundException("Membership not found")
        self.db.delete(obj)
        self.db.commit()
