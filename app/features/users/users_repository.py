from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.users.users_models import User


class UserRepository(CrudRepository[User]):

    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_id_relations(self):
        return [
            lambda: selectinload(User.wallet),
            lambda: selectinload(User.company),
        ]

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_username(self, username: str) -> Optional[User]:
        if not username:
            return None
        return self.db.query(User).filter(User.username == username).first()

    def delete_user(self, user_id: int) -> bool:
        db_user = self.get_by_id(user_id)
        if not db_user:
            return False
        self.db.delete(db_user)
        self.db.commit()
        return True
