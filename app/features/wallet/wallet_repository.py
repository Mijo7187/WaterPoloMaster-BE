from sqlalchemy.orm import Session

from app.common.crud.crud_repository import CrudRepository
from app.features.wallet.wallet_model import Wallet, WalletOwnerType


class WalletRepository(CrudRepository[Wallet]):
    def __init__(self, db: Session):
        super().__init__(db, Wallet)

    def get_by_owner(self, owner_id: int, owner_type: WalletOwnerType) -> Wallet | None:
        return (
            self.db.query(Wallet)
            .filter(Wallet.owner_id == owner_id, Wallet.owner_type == owner_type)
            .first()
        )
