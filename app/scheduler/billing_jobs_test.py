from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.features.contract.contract_model import ContractStatus, ContractType
from app.features.contract.contract_schemas import ContractCreate
from app.features.contract.contract_service import ContractService
from app.features.contract_installment.contract_installment_model import (
    ContractInstallment,
)
from app.features.contract_installment.contract_installment_service import (
    ContractInstallmentService,
)
from app.features.payment.payment_model import (
    PayableType,
    Payment,
    PaymentStatus,
    PaymentTypeCode,
)
from app.features.wallet.wallet_model import Wallet, WalletOwnerType
from app.scheduler.billing_jobs import (
    _monthly_staff_salary_job,
    _nightly_billing_job,
)


def _monthly(start_month, count, amount):
    """installments_list: `count` calendar-month installments from Jan 2026 on."""
    ends = [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]
    return [
        dict(
            period_start=date(2026, start_month + i, 1),
            period_end=ends[start_month - 1 + i],
            due_date=date(2026, start_month + i, 1),
            amount=Decimal(amount),
        )
        for i in range(count)
    ]


@pytest.fixture(autouse=True)
def _today(freeze_club_today):
    # Mid-January 2026: the Jan-Mar contracts below are ACTIVE when created.
    freeze_club_today(date(2026, 1, 15))


def _wallet_for(db_session, owner_id, owner_type, name):
    wallet = Wallet(owner_id=owner_id, owner_type=owner_type, name=name)
    db_session.add(wallet)
    db_session.commit()
    db_session.refresh(wallet)
    return wallet


@pytest.fixture()
def active_membership(db_session, create_company, create_user):
    """A club, a player, wallets on both, and an ACTIVE quarterly contract
    (Jan-Mar 2026) whose 15000 total is split into three 5000 installments."""
    def _create(with_user_wallet=True):
        company = create_company(name="Club")
        company.w_id = _wallet_for(
            db_session, company.id, WalletOwnerType.COMPANY, "Club"
        ).id

        user = create_user(company_id=company.id)
        if with_user_wallet:
            user.w_id = _wallet_for(
                db_session, user.id, WalletOwnerType.USER, "Player"
            ).id
        db_session.commit()

        service = ContractService(db_session)
        contract = service.create(ContractCreate(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.MEMBERSHIP,
            amount=Decimal("15000.00"),
            installments_list=_monthly(1, 3, "5000.00"),
        ))
        return company, user, contract
    return _create


def _installment_payments(db_session):
    return (
        db_session.query(Payment)
        .filter(Payment.payable_type == PayableType.CONTRACT_INSTALLMENT)
        .all()
    )


class TestNightlyBillingJob:

    def test_creates_pending_payments_for_due_installments(
        self, db_session, active_membership
    ):
        company, user, contract = active_membership()

        created = _nightly_billing_job(db_session, on_date=date(2026, 3, 31))

        assert created == 3
        payments = _installment_payments(db_session)
        assert len(payments) == 3
        for p in payments:
            assert p.payment_type == PaymentTypeCode.USER_MEMBERSHIP_FEE
            assert p.status == PaymentStatus.PENDING
            assert p.amount == Decimal("5000.00")
            # MEMBERSHIP flows user -> club; direction comes from the contract
            # type, never a stored flag.
            assert p.sender_wallet_id == user.w_id
            assert p.receiver_wallet_id == company.w_id

    def test_only_bills_installments_already_due(self, db_session, active_membership):
        active_membership()

        created = _nightly_billing_job(db_session, on_date=date(2026, 1, 15))

        assert created == 1
        assert len(_installment_payments(db_session)) == 1

    def test_job_is_idempotent(self, db_session, active_membership):
        active_membership()

        _nightly_billing_job(db_session, on_date=date(2026, 3, 31))
        second = _nightly_billing_job(db_session, on_date=date(2026, 3, 31))

        assert second == 0
        assert len(_installment_payments(db_session)) == 3

    def test_waived_installments_are_never_billed(self, db_session, active_membership):
        company, user, contract = active_membership()
        first = (
            db_session.query(ContractInstallment)
            .filter(ContractInstallment.contract_id == contract.id)
            .order_by(ContractInstallment.period_start)
            .first()
        )
        ContractInstallmentService(db_session).waive(first.id)

        created = _nightly_billing_job(db_session, on_date=date(2026, 3, 31))

        assert created == 2
        billed_ids = {p.payable_id for p in _installment_payments(db_session)}
        assert first.id not in billed_ids

    def test_draft_contracts_are_not_billed(self, db_session, active_membership):
        """Only ACTIVE contracts are billed by the nightly job."""
        company, user, contract = active_membership()
        from app.features.contract.contract_model import ContractStatus
        contract.status = ContractStatus.DRAFT
        db_session.commit()

        created = _nightly_billing_job(db_session, on_date=date(2026, 3, 31))

        assert created == 0

    def test_missing_wallet_is_skipped_not_fatal(self, db_session, active_membership):
        """One contract with no user wallet must not block billing for others."""
        active_membership(with_user_wallet=False)

        created = _nightly_billing_job(db_session, on_date=date(2026, 3, 31))

        assert created == 0
        assert len(_installment_payments(db_session)) == 0


@pytest.fixture()
def staff_contract(db_session, create_company, create_user, freeze_club_today):
    """A STAFF contract starting 2026-01-01 with NO installments yet — created
    "before" its start (so creation adds no month), then given `status` — so
    the tests drive generation purely through the job and a fixed `on_date`."""
    def _create(end_date=None, status=ContractStatus.ACTIVE, with_user_wallet=True):
        freeze_club_today(date(2025, 12, 15))
        company = create_company(name="Club")
        company.w_id = _wallet_for(
            db_session, company.id, WalletOwnerType.COMPANY, "Club"
        ).id
        user = create_user(company_id=company.id)
        if with_user_wallet:
            user.w_id = _wallet_for(
                db_session, user.id, WalletOwnerType.USER, "Coach"
            ).id
        db_session.commit()

        contract = ContractService(db_session).create(ContractCreate(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.STAFF,
            amount=Decimal("120000.00"),
            start_date=date(2026, 1, 1),
            end_date=end_date,
        ))
        contract.status = status
        db_session.commit()
        return company, user, contract
    return _create


def _periods(db_session, contract):
    return [
        (i.period_start, i.period_end)
        for i in db_session.query(ContractInstallment)
        .filter(ContractInstallment.contract_id == contract.id)
        .order_by(ContractInstallment.period_start)
        .all()
    ]


class TestMonthlyStaffSalaryJob:

    def test_adds_the_calendar_month_and_its_payment(
        self, db_session, staff_contract
    ):
        company, user, contract = staff_contract()

        created = _monthly_staff_salary_job(db_session, on_date=date(2026, 2, 1))

        assert created == 1
        assert _periods(db_session, contract) == [
            (date(2026, 2, 1), date(2026, 2, 28)),
        ]
        [installment] = db_session.query(ContractInstallment).filter(
            ContractInstallment.contract_id == contract.id
        ).all()
        assert installment.amount == Decimal("120000.00")
        assert installment.due_date == date(2026, 2, 1)

        [payment] = _installment_payments(db_session)
        assert payment.payable_id == installment.id
        assert payment.status == PaymentStatus.PENDING
        assert payment.payment_type == PaymentTypeCode.CLUB_SALARY_USER
        assert payment.amount == Decimal("120000.00")
        # STAFF flows club -> user.
        assert payment.sender_wallet_id == company.w_id
        assert payment.receiver_wallet_id == user.w_id

    def test_is_idempotent(self, db_session, staff_contract):
        _, _, contract = staff_contract()
        _monthly_staff_salary_job(db_session, on_date=date(2026, 2, 1))

        second = _monthly_staff_salary_job(db_session, on_date=date(2026, 2, 1))

        assert second == 0
        assert len(_periods(db_session, contract)) == 1
        assert len(_installment_payments(db_session)) == 1

    def test_each_run_adds_its_own_month(self, db_session, staff_contract):
        _, _, contract = staff_contract()

        _monthly_staff_salary_job(db_session, on_date=date(2026, 1, 1))
        _monthly_staff_salary_job(db_session, on_date=date(2026, 2, 1))

        assert _periods(db_session, contract) == [
            (date(2026, 1, 1), date(2026, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
        ]
        assert len(_installment_payments(db_session)) == 2

    def test_a_month_before_the_start_date_is_skipped(
        self, db_session, staff_contract
    ):
        _, _, contract = staff_contract()

        assert _monthly_staff_salary_job(db_session, on_date=date(2025, 12, 1)) == 0
        assert _periods(db_session, contract) == []

    def test_a_month_after_the_end_date_is_skipped(self, db_session, staff_contract):
        _, _, contract = staff_contract(end_date=date(2026, 3, 31))

        assert _monthly_staff_salary_job(db_session, on_date=date(2026, 4, 1)) == 0
        assert _periods(db_session, contract) == []

    def test_end_dated_contract_is_paid_through_its_last_month(
        self, db_session, staff_contract
    ):
        _, _, contract = staff_contract(end_date=date(2026, 3, 15))

        assert _monthly_staff_salary_job(db_session, on_date=date(2026, 3, 1)) == 1
        assert _periods(db_session, contract) == [
            (date(2026, 3, 1), date(2026, 3, 31)),
        ]

    def test_draft_contracts_are_left_alone(self, db_session, staff_contract):
        staff_contract(status=ContractStatus.DRAFT)

        assert _monthly_staff_salary_job(db_session, on_date=date(2026, 2, 1)) == 0

    def test_membership_is_not_auto_renewed(
        self, db_session, create_company, create_user
    ):
        """A MEMBERSHIP's schedule is fixed at signing; the job never adds to it."""
        company = create_company(name="Club")
        user = create_user(company_id=company.id)
        service = ContractService(db_session)
        contract = service.create(ContractCreate(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.MEMBERSHIP,
            amount=Decimal("5000.00"),
            installments_list=_monthly(1, 1, "5000.00"),
        ))
        before = _periods(db_session, contract)

        _monthly_staff_salary_job(db_session, on_date=date(2026, 2, 1))

        assert _periods(db_session, contract) == before

    def test_missing_wallet_keeps_the_month_for_the_nightly_job(
        self, db_session, staff_contract
    ):
        """No payment can be raised, but the month is still owed — the nightly
        job bills it once the wallet exists."""
        _, user, contract = staff_contract(with_user_wallet=False)

        _monthly_staff_salary_job(db_session, on_date=date(2026, 2, 1))

        assert _periods(db_session, contract) == [
            (date(2026, 2, 1), date(2026, 2, 28)),
        ]
        assert _installment_payments(db_session) == []

        user.w_id = _wallet_for(db_session, user.id, WalletOwnerType.USER, "Coach").id
        db_session.commit()

        assert _nightly_billing_job(db_session, on_date=date(2026, 2, 2)) == 1


class TestInstallmentPaymentStatus:

    def test_status_is_computed_from_payments(self, db_session, active_membership):
        company, user, contract = active_membership()
        service = ContractInstallmentService(db_session)

        installment = (
            db_session.query(ContractInstallment)
            .filter(ContractInstallment.contract_id == contract.id)
            .order_by(ContractInstallment.period_start)
            .first()
        )

        found = service.get_by_id(installment.id)
        assert found.payment_status == "pending"
        assert found.paid_amount == Decimal("0")

        # A partial, then a full settlement.
        db_session.add(Payment(
            sender_wallet_id=user.w_id,
            receiver_wallet_id=company.w_id,
            payment_type=PaymentTypeCode.USER_MEMBERSHIP_FEE,
            amount=Decimal("2000.00"),
            status=PaymentStatus.COMPLETED,
            payable_type=PayableType.CONTRACT_INSTALLMENT,
            payable_id=installment.id,
        ))
        db_session.commit()
        assert service.get_by_id(installment.id).payment_status == "partial"

        db_session.add(Payment(
            sender_wallet_id=user.w_id,
            receiver_wallet_id=company.w_id,
            payment_type=PaymentTypeCode.USER_MEMBERSHIP_FEE,
            amount=Decimal("3000.00"),
            status=PaymentStatus.COMPLETED,
            payable_type=PayableType.CONTRACT_INSTALLMENT,
            payable_id=installment.id,
        ))
        db_session.commit()
        assert service.get_by_id(installment.id).payment_status == "paid"

    def test_waived_short_circuits_status(self, db_session, active_membership):
        company, user, contract = active_membership()
        service = ContractInstallmentService(db_session)
        installment = (
            db_session.query(ContractInstallment)
            .filter(ContractInstallment.contract_id == contract.id)
            .first()
        )

        service.waive(installment.id)

        assert service.get_by_id(installment.id).payment_status == "waived"

    def test_list_endpoint_returns_the_computed_state(
        self, client, db_session, auth_headers
    ):
        """Regression: get_list attached the state, but the list schema used to
        drop it on the way out. Uses a partial payment to prove the value is
        really computed, not a default."""
        headers, user, company = auth_headers
        sender = _wallet_for(db_session, user.id, WalletOwnerType.USER, "Player")
        receiver = _wallet_for(db_session, company.id, WalletOwnerType.COMPANY, "Club")
        contract = ContractService(db_session).create(ContractCreate(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.MEMBERSHIP,
            amount=Decimal("5000.00"),
            installments_list=_monthly(1, 1, "5000.00"),
        ))
        installment = (
            db_session.query(ContractInstallment)
            .filter(ContractInstallment.contract_id == contract.id)
            .one()
        )
        db_session.add(Payment(
            sender_wallet_id=sender.id,
            receiver_wallet_id=receiver.id,
            payment_type=PaymentTypeCode.USER_MEMBERSHIP_FEE,
            amount=Decimal("2000.00"),
            status=PaymentStatus.COMPLETED,
            payable_type=PayableType.CONTRACT_INSTALLMENT,
            payable_id=installment.id,
        ))
        db_session.commit()

        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            resp = client.get(
                f"/api/contract-installment/?contract_id={contract.id}",
                headers=headers,
            )

        assert resp.status_code == 200, resp.text
        [row] = resp.json()["data"]["items"]
        assert row["payment_status"] == "partial"
        assert Decimal(str(row["paid_amount"])) == Decimal("2000.00")
