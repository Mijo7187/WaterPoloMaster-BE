import uuid
import pytest

from app.features.wallet.wallet_model import Wallet, WalletOwnerType
from app.features.wallet.wallet_repository import WalletRepository
from app.features.wallet.wallet_service import WalletService
from app.features.wallet.wallet_schemas import WalletCreate, WalletUpdate
from app.core.api.exceptions import NotFoundException


# ── Repository ───────────────────────────────────────────────

class TestWalletRepository:

    def test_create_wallet(self, db_session):
        repo = WalletRepository(db_session)
        wallet = repo.create({"owner_id": 1, "owner_type": WalletOwnerType.USER})
        assert wallet.id is not None
        assert isinstance(wallet.id, uuid.UUID)
        assert wallet.owner_type == WalletOwnerType.USER

    def test_get_by_id(self, db_session):
        repo = WalletRepository(db_session)
        wallet = repo.create({"owner_id": 1, "owner_type": WalletOwnerType.USER})
        found = repo.get_by_id(wallet.id)
        assert found is not None
        assert found.id == wallet.id

    def test_get_by_id_not_found(self, db_session):
        repo = WalletRepository(db_session)
        assert repo.get_by_id(uuid.uuid4()) is None

    def test_get_list(self, db_session):
        repo = WalletRepository(db_session)
        repo.create({"owner_id": 1, "owner_type": WalletOwnerType.USER})
        repo.create({"owner_id": 2, "owner_type": WalletOwnerType.COMPANY})
        from app.features.wallet.wallet_schemas import WalletFilters
        items, total = repo.get_list(filters=WalletFilters())
        assert total == 2

    def test_update_wallet(self, db_session):
        repo = WalletRepository(db_session)
        wallet = repo.create({"owner_id": 1, "owner_type": WalletOwnerType.USER})
        updated = repo.update(wallet.id, {"owner_type": WalletOwnerType.COMPANY})
        assert updated.owner_type == WalletOwnerType.COMPANY


# ── Service ──────────────────────────────────────────────────

class TestWalletService:

    def test_create_wallet(self, db_session):
        service = WalletService(db_session)
        wallet = service.create(WalletCreate(owner_id=1, owner_type=WalletOwnerType.USER))
        assert wallet.id is not None

    def test_get_by_id_not_found(self, db_session):
        service = WalletService(db_session)
        with pytest.raises(NotFoundException):
            service.get_by_id(uuid.uuid4())

    def test_get_summary_empty(self, db_session):
        service = WalletService(db_session)
        wallet = service.create(WalletCreate(owner_id=1, owner_type=WalletOwnerType.USER))
        summary = service.get_summary(wallet.id)
        assert summary["total_in_completed"] == 0
        assert summary["total_out_completed"] == 0
        assert summary["total_in_pending"] == 0
        assert summary["total_out_pending"] == 0
        assert summary["balance"] == 0
