# ============================================
# POLYMORPHIC RESOLVER TESTS
# ============================================

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.common.resolver.polymorphic_resolver import (
    resolve_payables,
    resolve_wallet_owners,
)
from app.features.payment.payment_model import (
    PayableType,
    Payment,
    PaymentStatus,
    PaymentTypeCode,
)
from app.features.wallet.wallet_model import Wallet, WalletOwnerType


@pytest.fixture()
def query_counter(db_session):
    """Count SQL statements issued inside the block — the resolver's whole
    promise is a bounded query count, so assert on it directly."""
    class Counter:
        def __init__(self):
            self.count = 0

    counter = Counter()
    engine = db_session.get_bind()

    def _before(conn, cursor, statement, params, context, executemany):
        counter.count += 1

    def _start():
        event.listen(engine, "before_cursor_execute", _before)
        counter.count = 0
        return counter

    def _stop():
        event.remove(engine, "before_cursor_execute", _before)

    counter.start = _start
    counter.stop = _stop
    return counter


def _wallet(db_session, owner_id, owner_type, name):
    w = Wallet(owner_id=owner_id, owner_type=owner_type, name=name)
    db_session.add(w)
    db_session.commit()
    db_session.refresh(w)
    return w


class TestResolvePayables:

    def test_resolves_trainings_and_tournaments_in_one_pass_each(
        self, db_session, create_company, create_training, query_counter
    ):
        club = create_company(name="Club")
        pool = create_company(name="Pool")
        club_wallet = _wallet(db_session, club.id, WalletOwnerType.COMPANY, "Club")
        pool_wallet = _wallet(db_session, pool.id, WalletOwnerType.COMPANY, "Pool")

        trainings = [
            create_training(company_id=club.id, pool_id=pool.id)
            for _ in range(5)
        ]

        for t in trainings:
            db_session.add(Payment(
                sender_wallet_id=club_wallet.id,
                receiver_wallet_id=pool_wallet.id,
                payment_type=PaymentTypeCode.CLUB_TRAINING_POOL,
                amount=Decimal("100.00"),
                status=PaymentStatus.PENDING,
                payable_type=PayableType.TRAINING,
                payable_id=t.id,
            ))
        db_session.commit()

        # Load them the way the list endpoint does — a committed ORM object is
        # expired, and re-reading its attributes would itself cost a query.
        payments = db_session.query(Payment).all()

        counter = query_counter.start()
        try:
            resolve_payables(db_session, payments)
        finally:
            query_counter.stop()

        assert all(p.payable is not None for p in payments)
        assert {p.payable.id for p in payments} == {t.id for t in trainings}

        # One type in play. The main IN query plus its selectinload follow-ups —
        # a fixed number, and crucially NOT one per payment row.
        assert counter.count < len(payments)

    def test_query_count_does_not_grow_with_list_size(
        self, db_session, create_company, create_training, query_counter
    ):
        """The N+1 guarantee: 3 rows and 12 rows must cost the same."""
        club = create_company(name="Club")
        pool = create_company(name="Pool")
        cw = _wallet(db_session, club.id, WalletOwnerType.COMPANY, "Club")
        pw = _wallet(db_session, pool.id, WalletOwnerType.COMPANY, "Pool")

        def _make(n):
            ids = []
            for _ in range(n):
                t = create_training(company_id=club.id, pool_id=pool.id)
                p = Payment(
                    sender_wallet_id=cw.id, receiver_wallet_id=pw.id,
                    payment_type=PaymentTypeCode.CLUB_TRAINING_POOL,
                    amount=Decimal("100.00"), status=PaymentStatus.PENDING,
                    payable_type=PayableType.TRAINING, payable_id=t.id,
                )
                db_session.add(p)
                ids.append(p)
            db_session.commit()
            return [db_session.query(Payment).filter(Payment.id == p.id).one() for p in ids]

        small = _make(3)
        counter = query_counter.start()
        try:
            resolve_payables(db_session, small)
        finally:
            query_counter.stop()
        small_queries = counter.count

        large = _make(12)
        counter = query_counter.start()
        try:
            resolve_payables(db_session, large)
        finally:
            query_counter.stop()
        large_queries = counter.count

        assert small_queries == large_queries

    def test_orphaned_payable_resolves_to_none(
        self, db_session, create_company, create_training
    ):
        """Target deleted, payment row remains — must not raise."""
        club = create_company(name="Club")
        pool = create_company(name="Pool")
        cw = _wallet(db_session, club.id, WalletOwnerType.COMPANY, "Club")
        pw = _wallet(db_session, pool.id, WalletOwnerType.COMPANY, "Pool")

        payment = Payment(
            sender_wallet_id=cw.id, receiver_wallet_id=pw.id,
            payment_type=PaymentTypeCode.CLUB_TRAINING_POOL,
            amount=Decimal("100.00"), status=PaymentStatus.PENDING,
            payable_type=PayableType.TRAINING,
            payable_id=999999,  # never existed
        )
        db_session.add(payment)
        db_session.commit()

        resolve_payables(db_session, [payment])
        assert payment.payable is None

    def test_ad_hoc_payment_with_no_payable(self, db_session, create_company):
        club = create_company(name="Club")
        cw = _wallet(db_session, club.id, WalletOwnerType.COMPANY, "Club")
        uw = _wallet(db_session, 1, WalletOwnerType.USER, "Someone")

        payment = Payment(
            sender_wallet_id=cw.id, receiver_wallet_id=uw.id,
            payment_type=PaymentTypeCode.CLUB_SALARY_USER,
            amount=Decimal("1000.00"), status=PaymentStatus.PENDING,
        )
        db_session.add(payment)
        db_session.commit()

        resolve_payables(db_session, [payment])
        assert payment.payable is None


class TestResolveWalletOwners:

    def test_resolves_mixed_user_and_company_owners(
        self, db_session, create_company, create_user
    ):
        company = create_company(name="Club")
        user = create_user(company_id=company.id)

        company_wallet = _wallet(
            db_session, company.id, WalletOwnerType.COMPANY, "Club"
        )
        user_wallet = _wallet(db_session, user.id, WalletOwnerType.USER, "Player")

        wallets = [company_wallet, user_wallet]
        resolve_wallet_owners(db_session, wallets)

        assert company_wallet.owner.id == company.id
        assert user_wallet.owner.id == user.id

    def test_orphaned_owner_resolves_to_none(self, db_session):
        wallet = _wallet(db_session, 999999, WalletOwnerType.USER, "Ghost")
        resolve_wallet_owners(db_session, [wallet])
        assert wallet.owner is None
