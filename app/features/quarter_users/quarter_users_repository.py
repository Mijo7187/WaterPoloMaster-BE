from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.quarter_users.quarter_users_model import QuarterUsers
from app.features.users.users_models import User


class QuarterUsersRepository(CrudRepository[QuarterUsers]):
    def __init__(self, db: Session):
        super().__init__(db, QuarterUsers)

    def get_list_relations(self):
        return [
            lambda: selectinload(QuarterUsers.user),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(QuarterUsers.user),
        ]

    def get_users_not_in_quarter(self, quarter_id: int, company_id: int, page: int = 1, size: int = 20):
        subq = (
            self.db.query(QuarterUsers.user_id)
            .filter(QuarterUsers.quarter_id == quarter_id)
            .subquery()
        )
        q = self.db.query(User).filter(
            ~User.id.in_(subq),
            User.company_id == company_id,
        )
        total = q.count()
        items = q.offset((page - 1) * size).limit(size).all()
        return items, total
