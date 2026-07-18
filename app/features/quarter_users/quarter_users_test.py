from decimal import Decimal

import pytest

from app.core.api.exceptions import BadRequestException, NotFoundException
from app.features.payment.payment_model import (
    Payment,
    PaymentStatus,
    PaymentTypeCode,
)
from app.features.quarter_users.quarter_users_model import QuarterUsers, TypeOfTraining
from app.features.quarter_users.quarter_users_schemas import QuarterUsersCreate
from app.features.quarter_users.quarter_users_service import QuarterUsersService
from app.features.wallet.wallet_model import Wallet, WalletOwnerType


@pytest.fixture()
def make_wallet(db_session):
    def _make(owner_id, owner_type):
        wallet = Wallet(owner_id=owner_id, owner_type=owner_type)
        db_session.add(wallet)
        db_session.commit()
        db_session.refresh(wallet)
        return wallet

    return _make


def _payments_for(db_session, quarter_id):
    return (
        db_session.query(Payment)
        .filter(Payment.quarter_id == quarter_id)
        .all()
    )


class TestQuarterUsersCreatePayment:
    def test_create_makes_pending_quarterly_fee_payment(
        self, db_session, create_company, create_user, create_quarter, make_wallet
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        quarter = create_quarter(
            company_id=company.id, waterpolo_price=15000, swimming_price=6000
        )
        user_wallet = make_wallet(user.id, WalletOwnerType.USER)
        club_wallet = make_wallet(company.id, WalletOwnerType.COMPANY)

        QuarterUsersService(db_session).create(
            QuarterUsersCreate(
                quarter_id=quarter.id,
                user_id=user.id,
                type_of_training=TypeOfTraining.WATERPOLO,
            )
        )

        payments = _payments_for(db_session, quarter.id)
        assert len(payments) == 1
        payment = payments[0]
        assert payment.payment_type == PaymentTypeCode.USER_QUARTERLY_FEE
        assert payment.status == PaymentStatus.PENDING
        assert payment.sender_wallet_id == user_wallet.id
        assert payment.receiver_wallet_id == club_wallet.id
        assert payment.amount == Decimal("15000")

    def test_amount_uses_swimming_price_for_swimming(
        self, db_session, create_company, create_user, create_quarter, make_wallet
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        quarter = create_quarter(
            company_id=company.id, waterpolo_price=15000, swimming_price=6000
        )
        make_wallet(user.id, WalletOwnerType.USER)
        make_wallet(company.id, WalletOwnerType.COMPANY)

        QuarterUsersService(db_session).create(
            QuarterUsersCreate(
                quarter_id=quarter.id,
                user_id=user.id,
                type_of_training=TypeOfTraining.SWIMMING,
            )
        )

        payment = _payments_for(db_session, quarter.id)[0]
        assert payment.amount == Decimal("6000")

    def test_zero_price_fails_and_creates_nothing(
        self, db_session, create_company, create_user, create_quarter, make_wallet
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        quarter = create_quarter(
            company_id=company.id, waterpolo_price=0, swimming_price=6000
        )
        make_wallet(user.id, WalletOwnerType.USER)
        make_wallet(company.id, WalletOwnerType.COMPANY)

        with pytest.raises(BadRequestException):
            QuarterUsersService(db_session).create(
                QuarterUsersCreate(
                    quarter_id=quarter.id,
                    user_id=user.id,
                    type_of_training=TypeOfTraining.WATERPOLO,
                )
            )

        assert _payments_for(db_session, quarter.id) == []
        assert db_session.query(QuarterUsers).count() == 0

    def test_missing_user_wallet_fails_and_creates_nothing(
        self, db_session, create_company, create_user, create_quarter, make_wallet
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        quarter = create_quarter(company_id=company.id)
        # only the club wallet exists
        make_wallet(company.id, WalletOwnerType.COMPANY)

        with pytest.raises(NotFoundException):
            QuarterUsersService(db_session).create(
                QuarterUsersCreate(
                    quarter_id=quarter.id,
                    user_id=user.id,
                    type_of_training=TypeOfTraining.WATERPOLO,
                )
            )

        assert _payments_for(db_session, quarter.id) == []
        assert db_session.query(QuarterUsers).count() == 0

    def test_delete_removes_pending_payment(
        self, db_session, create_company, create_user, create_quarter, make_wallet
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        quarter = create_quarter(company_id=company.id)
        make_wallet(user.id, WalletOwnerType.USER)
        make_wallet(company.id, WalletOwnerType.COMPANY)

        service = QuarterUsersService(db_session)
        obj = service.create(
            QuarterUsersCreate(
                quarter_id=quarter.id,
                user_id=user.id,
                type_of_training=TypeOfTraining.WATERPOLO,
            )
        )
        assert len(_payments_for(db_session, quarter.id)) == 1

        service.delete(obj.id)

        assert _payments_for(db_session, quarter.id) == []
        assert db_session.query(QuarterUsers).count() == 0
