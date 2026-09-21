from typing import Optional, Any

import bcrypt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import BadRequestException, ConflictException, NotFoundException
from app.features.company.company_repository import CompanyRepository
from app.features.users.users_models import User
from app.features.users.users_repository import UserRepository
from app.features.users.users_schemas import UserCreate


class UserService(CrudService[User]):

    def __init__(self, db: Session):
        super().__init__(db, UserRepository(db))

    # ── Password helpers ─────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    # ── Overrides ────────────────────────────────────

    def create(self, schema: UserCreate, current_user: Optional[Any] = None) -> User:
        from app.features.wallet.wallet_model import Wallet, WalletOwnerType

        errors = []
        if self.repository.get_user_by_email(schema.email):
            errors.append("Email already registered")
        if schema.username and self.repository.get_user_by_username(schema.username):
            errors.append("Username already taken")
        if errors:
            raise ConflictException(message=errors[0], errors=errors)

        if not CompanyRepository(self.db).get_by_id(schema.company_id):
            raise BadRequestException(message="Company not found")

        data = schema.model_dump(exclude={"password"})
        data["hashed_password"] = self.hash_password(schema.password)
        data["roles"] = [role.value for role in schema.roles]
        if schema.position is not None:
            data["position"] = [p.value for p in schema.position]
        if schema.default_team is not None:
            data["default_team"] = schema.default_team.value

        user = User(**data)
        self.db.add(user)
        self.db.flush()

        wallet = Wallet(
            owner_id=user.id,
            owner_type=WalletOwnerType.USER,
            name=f"{user.first_name} {user.last_name}",
        )
        self.db.add(wallet)
        self.db.flush()        # populate wallet.id before linking
        user.w_id = wallet.id
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, obj_id: int, schema: BaseModel, current_user: Optional[Any] = None) -> User:
        update_data = schema.model_dump(exclude_unset=True)

        errors = []
        for field_name, field_value in update_data.items():
            if field_value is None or (isinstance(field_value, str) and field_value.strip() == ""):
                errors.append(f"{field_name} cannot be empty if provided")
        if errors:
            raise BadRequestException(message=errors[0], errors=errors)

        existing = self.repository.get_by_id(obj_id)
        if not existing:
            raise NotFoundException("User not found")

        if "email" in update_data and update_data["email"] != existing.email:
            if self.repository.get_user_by_email(update_data["email"]):
                errors.append("Email already registered")
        if "username" in update_data and update_data["username"] != existing.username:
            if self.repository.get_user_by_username(update_data["username"]):
                errors.append("Username already taken")
        if errors:
            raise ConflictException(message=errors[0], errors=errors)

        if "password" in update_data:
            update_data["hashed_password"] = self.hash_password(update_data.pop("password"))

        if "roles" in update_data:
            update_data["roles"] = [r.value if hasattr(r, "value") else r for r in update_data["roles"]]

        if update_data.get("position") is not None:
            update_data["position"] = [
                p.value if hasattr(p, "value") else p for p in update_data["position"]
            ]

        if update_data.get("default_team") is not None:
            dt = update_data["default_team"]
            update_data["default_team"] = dt.value if hasattr(dt, "value") else dt

        obj = self.repository.update(obj_id, update_data)
        if not obj:
            raise NotFoundException("User not found")
        return obj

    # ── Extra methods ─────────────────────────────────

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.repository.get_user_by_email(email)

    def delete_user(self, user_id: int) -> bool:
        return self.repository.delete_user(user_id)

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = self.repository.get_user_by_email(email)
        if not user or not user.is_active:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user
