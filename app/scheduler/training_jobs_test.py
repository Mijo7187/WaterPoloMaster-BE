from datetime import date, time

import pytest

from app.features.payment.payment_model import (
    PayableType,
    Payment,
    PaymentStatus,
    PaymentTypeCode,
)
from app.features.training.training_model import TrainingStatus
from app.features.wallet.wallet_model import Wallet, WalletOwnerType
from app.scheduler.training_jobs import _nightly_training_job


def _training_payments(db_session, training_id=None):
    """Payments pointing at a training via the polymorphic payable pair."""
    q = db_session.query(Payment).filter(
        Payment.payable_type == PayableType.TRAINING
    )
    if training_id is not None:
        q = q.filter(Payment.payable_id == training_id)
    return q.all()


@pytest.fixture()
def club_and_pool(db_session, create_company):
    """A club and a pool, each with a wallet wired up via Company.w_id."""
    def _create():
        club = create_company(name="Club")
        pool = create_company(name="Pool")
        for company, owner_type in ((club, WalletOwnerType.COMPANY), (pool, WalletOwnerType.COMPANY)):
            wallet = Wallet(owner_id=company.id, owner_type=owner_type, name=company.name)
            db_session.add(wallet)
            db_session.commit()
            db_session.refresh(wallet)
            company.w_id = wallet.id
        db_session.commit()
        return club, pool
    return _create


class TestNightlyTrainingJob:
    def test_payment_points_at_the_training(
        self, db_session, club_and_pool, create_training
    ):
        club, pool = club_and_pool()
        training = create_training(
            company_id=club.id,
            pool_id=pool.id,
            training_date=date(2026, 4, 1),
            end_time=time(11, 0),
            price=250,
        )

        _nightly_training_job(db_session)

        payments = _training_payments(db_session, training.id)
        assert len(payments) == 1
        payment = payments[0]
        assert payment.payable_type == PayableType.TRAINING
        assert payment.payable_id == training.id
        assert payment.payment_type == PaymentTypeCode.CLUB_TRAINING_POOL
        assert payment.status == PaymentStatus.PENDING
        assert payment.sender_wallet_id == club.w_id
        assert payment.receiver_wallet_id == pool.w_id

    def test_past_training_is_marked_finished(
        self, db_session, club_and_pool, create_training
    ):
        club, pool = club_and_pool()
        training = create_training(
            company_id=club.id, pool_id=pool.id, training_date=date(2026, 4, 1)
        )
        assert training.status == TrainingStatus.INCOMING.value

        _nightly_training_job(db_session)

        db_session.refresh(training)
        assert training.status == TrainingStatus.FINISHED.value

    def test_job_is_idempotent(self, db_session, club_and_pool, create_training):
        club, pool = club_and_pool()
        training = create_training(
            company_id=club.id, pool_id=pool.id, training_date=date(2026, 4, 1)
        )

        _nightly_training_job(db_session)
        _nightly_training_job(db_session)

        assert len(_training_payments(db_session, training.id)) == 1

    def test_two_identical_trainings_same_day_each_get_a_payment(
        self, db_session, club_and_pool, create_training
    ):
        """Same club, pool, date and price — the old description-based guard
        collapsed these into a single payment."""
        club, pool = club_and_pool()
        first = create_training(
            company_id=club.id, pool_id=pool.id, training_date=date(2026, 4, 1), price=100
        )
        second = create_training(
            company_id=club.id, pool_id=pool.id, training_date=date(2026, 4, 1), price=100
        )

        _nightly_training_job(db_session)

        training_ids = {p.payable_id for p in _training_payments(db_session)}
        assert training_ids == {first.id, second.id}

    def test_bad_wallet_owner_type_is_skipped_not_fatal(
        self, db_session, create_company, create_training, club_and_pool
    ):
        """A pool whose wallet is owned by a USER (not a COMPANY) fails
        CLUB_TRAINING_POOL's wallet spec. The job logs and moves on rather than
        aborting: one unbillable training must not block the rest of the batch."""
        good_club, good_pool = club_and_pool()
        good_training = create_training(
            company_id=good_club.id, pool_id=good_pool.id, training_date=date(2026, 4, 1)
        )

        bad_club = create_company(name="Bad Club")
        bad_pool = create_company(name="Bad Pool")
        club_wallet = Wallet(owner_id=bad_club.id, owner_type=WalletOwnerType.COMPANY)
        bad_wallet = Wallet(owner_id=bad_pool.id, owner_type=WalletOwnerType.USER)
        db_session.add_all([club_wallet, bad_wallet])
        db_session.commit()
        bad_club.w_id, bad_pool.w_id = club_wallet.id, bad_wallet.id
        db_session.commit()

        bad_training = create_training(
            company_id=bad_club.id, pool_id=bad_pool.id, training_date=date(2026, 4, 1)
        )

        # Does not raise.
        _nightly_training_job(db_session)

        assert len(_training_payments(db_session, bad_training.id)) == 0
        assert len(_training_payments(db_session, good_training.id)) == 1
