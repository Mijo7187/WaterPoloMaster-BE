import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from app.features.payment.payment_model import Payment, PaymentStatus, PaymentTypeCode
from app.features.payment.payment_schemas import PaymentFilters
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
