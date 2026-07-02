from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.features.company.company_model import Company
from app.features.company.company_repository import CompanyRepository


class CompanyService(CrudService[Company]):
    def __init__(self, db: Session):
        super().__init__(db, CompanyRepository(db))

    def create(self, schema: BaseModel, current_user: Optional[Any] = None) -> Company:
        from app.features.wallet.wallet_model import Wallet, WalletOwnerType

        data = schema.model_dump()
        company = Company(**data)
        self.db.add(company)
        self.db.flush()

        wallet = Wallet(owner_id=company.id, owner_type=WalletOwnerType.COMPANY, name=company.name)
        self.db.add(wallet)
        self.db.flush()            # populate wallet.id before linking
        company.w_id = wallet.id   # the missing link
        self.db.commit()
        self.db.refresh(company)
        return company
