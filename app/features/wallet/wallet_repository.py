from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.wallet.wallet_model import Wallet


class WalletRepository(CrudRepository[Wallet]):
    def __init__(self, db: Session):
        super().__init__(db, Wallet)
