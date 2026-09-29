# ============================================
# MEMBERSHIP REPOSITORY - Database Operations
# ============================================

from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.membership.membership_model import Membership
from app.features.sifarnici.selection.selection_model import Selection


class MembershipRepository(CrudRepository[Membership]):
    def __init__(self, db: Session):
        super().__init__(db, Membership)

    def get_list_relations(self):
        # Both response schemas nest the selection, so both queries load it.
        return [
            lambda: selectinload(Membership.selection),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Membership.selection),
        ]

    def get_selection(self, selection_id: int) -> Optional[Selection]:
        return self.db.get(Selection, selection_id)

    def find_duplicate(
        self,
        company_id: int,
        selection_id: int,
        program,
        billing_type,
        exclude_id: Optional[int] = None,
    ) -> Optional[Membership]:
        """The row already holding this catalog key, if any.

        Backs UNIQUE(company_id, selection_id, program, billing_type) with a
        readable 409 instead of a raw IntegrityError.
        """
        q = self.db.query(Membership).filter(
            Membership.company_id == company_id,
            Membership.selection_id == selection_id,
            Membership.program == program,
            Membership.billing_type == billing_type,
        )
        if exclude_id is not None:
            q = q.filter(Membership.id != exclude_id)
        return q.first()
