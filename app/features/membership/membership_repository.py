# ============================================
# MEMBERSHIP REPOSITORY - Database Operations
# ============================================

from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.membership.membership_model import Membership


class MembershipRepository(CrudRepository[Membership]):
    def __init__(self, db: Session):
        super().__init__(db, Membership)
