import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.api.exceptions import BadRequestException, NotFoundException
from app.features.payment.payment_model import (
    PayableType,
    Payment,
    PaymentStatus,
    PaymentTypeCode,
)
from app.features.payment.payment_schemas import PaymentCreate, PaymentFilters
from app.features.payment.payment_service import PaymentService
from app.features.wallet.wallet_model import Wallet, WalletOwnerType


@pytest.fixture()
def wallets(db_session):
    sender = Wallet(owner_id=1, owner_type=WalletOwnerType.USER)
    receiver = Wallet(owner_id=1, owner_type=WalletOwnerType.COMPANY)
    db_session.add_all([sender, receiver])
    db_session.commit()
    return sender, receiver


def test_payment_list_defaults_to_newest_first(db_session, wallets):
    sender, receiver = wallets
    # Insert out of chronological order.
    for day in (1, 7, 4):
        db_session.add(
            Payment(
                id=uuid.uuid4(),
                sender_wallet_id=sender.id,
                receiver_wallet_id=receiver.id,
                payment_type=PaymentTypeCode.CLUB_SALARY_USER,
                amount=Decimal("10.00"),
                status=PaymentStatus.PENDING,
                created_at=datetime(2026, 7, day, 10, 0),
            )
        )
    db_session.commit()

    items, total = PaymentService(db_session).get_list(filters=PaymentFilters())

    assert total == 3
    assert [i.created_at.day for i in items] == [7, 4, 1]


def _payment(sender_id, receiver_id, day):
    return Payment(
        id=uuid.uuid4(),
        sender_wallet_id=sender_id,
        receiver_wallet_id=receiver_id,
        payment_type=PaymentTypeCode.CLUB_SALARY_USER,
        amount=Decimal("10.00"),
        status=PaymentStatus.PENDING,
        created_at=datetime(2026, 7, day, 10, 0),
    )


def test_wallet_id_filter_matches_sender_or_receiver(db_session, wallets):
    a, b = wallets
    other = Wallet(owner_id=2, owner_type=WalletOwnerType.COMPANY)
    db_session.add(other)
    db_session.commit()

    db_session.add_all([
        _payment(a.id, b.id, 1),      # a is sender
        _payment(other.id, a.id, 2),  # a is receiver
        _payment(other.id, b.id, 3),  # a not involved
    ])
    db_session.commit()

    # wallet_id returns the union of both directions, excluding the unrelated one.
    _, total = PaymentService(db_session).get_list(filters=PaymentFilters(wallet_id=a.id))
    assert total == 2

    # Combining with receiver_wallet_id narrows the union down (AND on top of OR).
    _, narrowed = PaymentService(db_session).get_list(
        filters=PaymentFilters(wallet_id=a.id, receiver_wallet_id=a.id)
    )
    assert narrowed == 1


# ============================================
# POLYMORPHIC PAYABLE — the app-layer integrity guard
# ============================================
# payable_id has no DB foreign key by design, so PAYMENT_TYPE_SPECS plus these
# service-level checks are what stand in for it.

class TestPayableValidation:

    def _create(self, db_session, sender, receiver, **kwargs):
        base = dict(
            sender_wallet_id=sender.id,
            receiver_wallet_id=receiver.id,
            amount=Decimal("100.00"),
            status=PaymentStatus.PENDING,
        )
        base.update(kwargs)
        return PaymentService(db_session).create(PaymentCreate(**base))

    def test_wrong_payable_type_for_the_payment_type_is_rejected(
        self, db_session, wallets, create_company, create_training
    ):
        sender, receiver = wallets
        club = create_company(name="Club")
        training = create_training(company_id=club.id)

        # USER_TOURNAMENT_FEE demands a tournament, not a training.
        with pytest.raises(BadRequestException, match="requires payable_type"):
            self._create(
                db_session, sender, receiver,
                payment_type=PaymentTypeCode.USER_TOURNAMENT_FEE,
                payable_type=PayableType.TRAINING,
                payable_id=training.id,
            )

    def test_missing_payable_is_rejected(self, db_session, wallets):
        sender, receiver = wallets
        with pytest.raises(BadRequestException, match="requires a payable of type"):
            self._create(
                db_session, sender, receiver,
                payment_type=PaymentTypeCode.USER_TOURNAMENT_FEE,
            )

    def test_nonexistent_payable_id_is_rejected(self, db_session, wallets):
        """The existence check that replaces the foreign key."""
        sender, receiver = wallets
        with pytest.raises(NotFoundException, match="No tournament with id"):
            self._create(
                db_session, sender, receiver,
                payment_type=PaymentTypeCode.USER_TOURNAMENT_FEE,
                payable_type=PayableType.TOURNAMENT,
                payable_id=999999,
            )

    def test_salary_must_point_at_a_contract_installment(
        self, db_session, wallets, create_company, create_training
    ):
        """CLUB_SALARY_USER pays a STAFF contract_installment — nothing else."""
        sender, receiver = wallets
        club = create_company(name="Club")
        training = create_training(company_id=club.id)

        with pytest.raises(BadRequestException, match="requires payable_type"):
            self._create(
                db_session, receiver, sender,  # company -> user
                payment_type=PaymentTypeCode.CLUB_SALARY_USER,
                payable_type=PayableType.TRAINING,
                payable_id=training.id,
            )

    def test_half_a_payable_pair_is_rejected_by_the_schema(self):
        with pytest.raises(ValidationError, match="must be provided together"):
            PaymentCreate(
                sender_wallet_id=uuid.uuid4(),
                receiver_wallet_id=uuid.uuid4(),
                payment_type=PaymentTypeCode.USER_TOURNAMENT_FEE,
                amount=Decimal("10.00"),
                payable_type=PayableType.TOURNAMENT,
                # payable_id deliberately omitted
            )

    def test_valid_payable_is_accepted(
        self, db_session, wallets, create_company, create_training
    ):
        sender, receiver = wallets
        club = create_company(name="Club")
        training = create_training(company_id=club.id)

        payment = self._create(
            db_session, receiver, receiver,  # company -> company
            payment_type=PaymentTypeCode.CLUB_TRAINING_POOL,
            payable_type=PayableType.TRAINING,
            payable_id=training.id,
        )
        assert payment.payable_type == PayableType.TRAINING
        assert payment.payable_id == training.id


# ============================================
# COMPANY SCOPE
# ============================================
# Payment has no company_id: it belongs to a company when either wallet is the
# company's own wallet or a wallet of one of its users.

def _call(client, method, url, headers, **kwargs):
    from unittest.mock import patch
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


class TestPaymentCompanyScope:

    @pytest.fixture()
    def scoped(self, db_session, create_company, create_user, auth_headers):
        headers, admin, company = auth_headers
        other = create_company(name="Other Club")
        other_user = create_user(email="other@test.com", username="other", company_id=other.id)

        w = {
            "my_company": Wallet(owner_id=company.id, owner_type=WalletOwnerType.COMPANY),
            "my_user": Wallet(owner_id=admin.id, owner_type=WalletOwnerType.USER),
            "other_company": Wallet(owner_id=other.id, owner_type=WalletOwnerType.COMPANY),
            "other_user": Wallet(owner_id=other_user.id, owner_type=WalletOwnerType.USER),
        }
        db_session.add_all(w.values())
        db_session.commit()

        p = {
            "mine": _payment(w["my_user"].id, w["my_company"].id, 1),
            "cross": _payment(w["other_company"].id, w["my_company"].id, 2),
            "theirs": _payment(w["other_user"].id, w["other_company"].id, 3),
        }
        db_session.add_all(p.values())
        db_session.commit()
        return headers, admin, w, p

    def test_list_only_payments_involving_own_company(self, client, scoped):
        headers, _, _, p = scoped
        response = _call(client, "get", "/api/payment/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert ids == {str(p["mine"].id), str(p["cross"].id)}

    def test_get_other_company_payment_403(self, client, scoped):
        headers, _, _, p = scoped
        response = _call(client, "get", f"/api/payment/{p['theirs'].id}", headers)
        assert response.status_code == 403

    def test_get_own_company_payment(self, client, scoped):
        headers, _, _, p = scoped
        response = _call(client, "get", f"/api/payment/{p['mine'].id}", headers)
        assert response.status_code == 200

    def test_super_admin_sees_all_payments(self, client, scoped, super_admin_headers):
        _, _, _, p = scoped
        headers, _ = super_admin_headers
        response = _call(client, "get", f"/api/payment/{p['theirs'].id}", headers)
        assert response.status_code == 200

    def test_create_between_other_company_wallets_forbidden(
        self, db_session, scoped, create_training
    ):
        from app.core.api.exceptions import ForbiddenException

        _, admin, w, _ = scoped
        training = create_training(company_id=w["other_company"].owner_id)
        with pytest.raises(ForbiddenException):
            PaymentService(db_session).create(
                PaymentCreate(
                    sender_wallet_id=w["other_company"].id,
                    receiver_wallet_id=w["other_company"].id,
                    payment_type=PaymentTypeCode.CLUB_TRAINING_POOL,
                    amount=Decimal("10.00"),
                    payable_type=PayableType.TRAINING,
                    payable_id=training.id,
                ),
                current_user=admin,
            )
