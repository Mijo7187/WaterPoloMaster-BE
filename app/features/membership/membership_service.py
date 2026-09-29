# ============================================
# MEMBERSHIP SERVICE - Business Logic
# ============================================

from typing import Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudHooks
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.features.membership.membership_model import BillingType, Membership
from app.features.membership.membership_repository import MembershipRepository
from app.features.users.users_models import User, UserRole


def _validate_term_months(billing_type, term_months) -> None:
    """The same rule the Pydantic validator enforces, re-checked against the
    MERGED row on update — a patch that sends only `billing_type` cannot be
    validated by the schema alone."""
    if billing_type is None:
        return
    if BillingType(billing_type) == BillingType.TERM:
        if term_months is None or term_months < 1:
            raise ValidationException(
                ["term_months"],
                "term_months is required and must be at least 1 when "
                "billing_type is TERM.",
            )
    elif term_months is not None:
        raise ValidationException(
            ["term_months"],
            "term_months must be null when billing_type is MONTHLY.",
        )


def _validate_selection(db, company_id, selection_id) -> None:
    """A plan prices one of ITS OWN club's selections."""
    if company_id is None or selection_id is None:
        return

    selection = MembershipRepository(db).get_selection(selection_id)
    if not selection:
        raise NotFoundException("Selection not found")
    if selection.company_id != company_id:
        raise ValidationException(
            ["selection_id"],
            "The selection belongs to a different company than the membership.",
        )


def _assert_unique(
    db, company_id, selection_id, program, billing_type,
    exclude_id: Optional[int] = None,
) -> None:
    """Enforce UNIQUE(company_id, selection_id, program, billing_type) with a
    readable 409. Checked on update as well as create — leaving it to the DB
    constraint would surface a raw IntegrityError instead."""
    if None in (company_id, selection_id, program, billing_type):
        return

    if MembershipRepository(db).find_duplicate(
        company_id, selection_id, program, billing_type, exclude_id=exclude_id
    ):
        raise ConflictException(
            "This company already has a membership for that selection, "
            "program and billing type."
        )


def _membership_pre_create(
    data: dict, db, current_user: Optional[User] = None
) -> dict:
    _validate_term_months(data.get("billing_type"), data.get("term_months"))
    _validate_selection(db, data.get("company_id"), data.get("selection_id"))
    _assert_unique(
        db,
        data.get("company_id"),
        data.get("selection_id"),
        data.get("program"),
        data.get("billing_type"),
    )
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
        company_id = data.get("company_id", existing.company_id)
        selection_id = data.get("selection_id", existing.selection_id)
        billing_type = data.get("billing_type", existing.billing_type)
        term_months = data.get("term_months", existing.term_months)

        # Switching TERM -> MONTHLY drops the block length rather than failing
        # on a leftover the caller never sent. (The other direction is caught
        # by the schema: billing_type=TERM without term_months is a 422.)
        if (
            billing_type is not None
            and BillingType(billing_type) == BillingType.MONTHLY
            and term_months is not None
        ):
            term_months = None
            data["term_months"] = None

        _validate_term_months(billing_type, term_months)
        _validate_selection(db, company_id, selection_id)
        _assert_unique(
            db,
            company_id,
            selection_id,
            data.get("program", existing.program),
            billing_type,
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
