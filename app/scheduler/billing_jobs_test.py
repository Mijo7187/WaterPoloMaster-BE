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
from app.features.membership.membership_model import BillingType, Program
from app.features.membership.membership_schemas import MembershipCreate
from app.features.membership.membership_service import MembershipService
from app.features.payment.payment_model import (
    PayableType,
    Payment,
    PaymentStatus,
    PaymentTypeCode,
)
from app.features.sifarnici.selection.selection_model import Selection
from app.features.wallet.wallet_model import Wallet, WalletOwnerType
from app.scheduler.billing_jobs import (
    _daily_debt_job,
    _monthly_recurring_billing_job,
    _nightly_billing_job,
)


@pytest.fixture(autouse=True)
def _today(freeze_club_today):
    # Mid-January 2026 unless a fixture moves it.
    freeze_club_today(date(2026, 1, 15))


def _wallet_for(db_session, owner_id, owner_type, name):
    wallet = Wallet(owner_id=owner_id, owner_type=owner_type, name=name)
    db_session.add(wallet)
    db_session.commit()
    db_session.refresh(wallet)
    return wallet


def _selection(db_session, company_id, name="U15"):
    selection = Selection(company_id=company_id, name=name)
    db_session.add(selection)
    db_session.commit()
    db_session.refresh(selection)
    return selection


def _plan(db_session, company, selection, **kwargs):
    payload = dict(
        company_id=company.id,
        selection_id=selection.id,
        name="Plan",
        program=Program.WATERPOLO,
        billing_type=BillingType.MONTHLY,
        price=Decimal("5000.00"),
    )
    payload.update(kwargs)
    return MembershipService(db_session).create(MembershipCreate(**payload))


def _installment_payments(db_session):
    return (
        db_session.query(Payment)
        .filter(Payment.payable_type == PayableType.CONTRACT_INSTALLMENT)
        .all()
    )


def _periods(db_session, contract):
    return [
        (i.period_start, i.period_end)
        for i in db_session.query(ContractInstallment)
        .filter(ContractInstallment.contract_id == contract.id)
        .order_by(ContractInstallment.period_start)
        .all()
    ]


@pytest.fixture()
def unbilled_membership(db_session, create_company, create_user):
    """A MONTHLY membership whose installments exist but carry NO payment.

    The player has no wallet, so generation writes the periods and the payment
    cannot be raised — exactly the state the nightly job exists to clear. The
    wallet is added afterwards by the tests that need billing to succeed.
    """
    def _create(months=3):
        company = create_company(name="Club")
        company.w_id = _wallet_for(
            db_session, company.id, WalletOwnerType.COMPANY, "Club"
        ).id
        user = create_user(company_id=company.id)
        db_session.commit()

        plan = _plan(db_session, company, _selection(db_session, company.id))
        contract = ContractService(db_session).create(ContractCreate(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.MEMBERSHIP,
            membership_id=plan.id,
            start_date=date(2026, 1, 1),
        ))
        # One period per month, none of them billed (no user wallet yet).
        for month in range(1, months + 1):
            _monthly_recurring_billing_job(db_session, on_date=date(2026, month, 1))

        assert _installment_payments(db_session) == []
        return company, user, contract

    return _create


def _give_user_wallet(db_session, user):
    user.w_id = _wallet_for(db_session, user.id, WalletOwnerType.USER, "Player").id
    db_session.commit()


class TestNightlyBillingJob:
    """Turns due, unbilled installments into PENDING payments. Under recurring
    billing the payment is normally raised at generation time, so this job is
    the safety net for the ones that could not be."""

    def test_creates_pending_payments_for_due_installments(
        self, db_session, unbilled_membership
    ):
        company, user, contract = unbilled_membership()
        _give_user_wallet(db_session, user)

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

    def test_only_bills_installments_already_due(
        self, db_session, unbilled_membership
    ):
        _, user, _ = unbilled_membership()
        _give_user_wallet(db_session, user)

        created = _nightly_billing_job(db_session, on_date=date(2026, 1, 15))

        assert created == 1
        assert len(_installment_payments(db_session)) == 1

    def test_job_is_idempotent(self, db_session, unbilled_membership):
        _, user, _ = unbilled_membership()
        _give_user_wallet(db_session, user)

        _nightly_billing_job(db_session, on_date=date(2026, 3, 31))
        second = _nightly_billing_job(db_session, on_date=date(2026, 3, 31))

        assert second == 0
        assert len(_installment_payments(db_session)) == 3

    def test_waived_installments_are_never_billed(
        self, db_session, unbilled_membership
    ):
        _, user, contract = unbilled_membership()
        _give_user_wallet(db_session, user)
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

    def test_draft_contracts_are_not_billed(self, db_session, unbilled_membership):
        """Only ACTIVE contracts are billed by the nightly job."""
        _, user, contract = unbilled_membership()
        _give_user_wallet(db_session, user)
        contract.status = ContractStatus.DRAFT
        db_session.commit()

        assert _nightly_billing_job(db_session, on_date=date(2026, 3, 31)) == 0

    def test_missing_wallet_is_skipped_not_fatal(
        self, db_session, unbilled_membership
    ):
        """One contract with no user wallet must not block billing for others."""
        unbilled_membership()  # wallet deliberately never added

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


@pytest.fixture()
def monthly_membership_contract(
    db_session, create_company, create_user, freeze_club_today
):
    """The MEMBERSHIP MONTHLY mirror of `staff_contract`: open-ended, created
    before its start so the job alone drives generation."""
    def _create(status=ContractStatus.ACTIVE):
        freeze_club_today(date(2025, 12, 15))
        company = create_company(name="Club")
        company.w_id = _wallet_for(
            db_session, company.id, WalletOwnerType.COMPANY, "Club"
        ).id
        user = create_user(company_id=company.id)
        user.w_id = _wallet_for(
            db_session, user.id, WalletOwnerType.USER, "Player"
        ).id
        db_session.commit()

        plan = _plan(db_session, company, _selection(db_session, company.id))
        contract = ContractService(db_session).create(ContractCreate(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.MEMBERSHIP,
            membership_id=plan.id,
            start_date=date(2026, 1, 1),
        ))
        contract.status = status
        db_session.commit()
        return company, user, contract
    return _create


class TestMonthlyRecurringBillingJob:
    """STAFF salaries and MEMBERSHIP MONTHLY dues — the same shape, one period
    of `contract.amount` per ACTIVE month."""

    def test_adds_the_calendar_month_and_its_payment(
        self, db_session, staff_contract
    ):
        company, user, contract = staff_contract()

        created = _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1))

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
        _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1))

        second = _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1))

        assert second == 0
        assert len(_periods(db_session, contract)) == 1
        assert len(_installment_payments(db_session)) == 1

    def test_each_run_adds_its_own_month(self, db_session, staff_contract):
        _, _, contract = staff_contract()

        _monthly_recurring_billing_job(db_session, on_date=date(2026, 1, 1))
        _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1))

        assert _periods(db_session, contract) == [
            (date(2026, 1, 1), date(2026, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
        ]
        assert len(_installment_payments(db_session)) == 2

    def test_a_month_before_the_start_date_is_skipped(
        self, db_session, staff_contract
    ):
        _, _, contract = staff_contract()

        assert _monthly_recurring_billing_job(db_session, on_date=date(2025, 12, 1)) == 0
        assert _periods(db_session, contract) == []

    def test_a_month_after_the_end_date_is_skipped(self, db_session, staff_contract):
        _, _, contract = staff_contract(end_date=date(2026, 3, 31))

        assert _monthly_recurring_billing_job(db_session, on_date=date(2026, 4, 1)) == 0
        assert _periods(db_session, contract) == []

    def test_end_dated_contract_is_paid_through_its_last_month(
        self, db_session, staff_contract
    ):
        _, _, contract = staff_contract(end_date=date(2026, 3, 15))

        assert _monthly_recurring_billing_job(db_session, on_date=date(2026, 3, 1)) == 1
        assert _periods(db_session, contract) == [
            (date(2026, 3, 1), date(2026, 3, 31)),
        ]

    def test_draft_contracts_are_left_alone(self, db_session, staff_contract):
        staff_contract(status=ContractStatus.DRAFT)

        assert _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1)) == 0

    # ── MEMBERSHIP MONTHLY: the mirror of STAFF ─────────────────────

    def test_monthly_membership_gets_its_month_and_payment(
        self, db_session, monthly_membership_contract
    ):
        company, user, contract = monthly_membership_contract()

        created = _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1))

        assert created == 1
        assert _periods(db_session, contract) == [
            (date(2026, 2, 1), date(2026, 2, 28)),
        ]
        [payment] = _installment_payments(db_session)
        assert payment.amount == Decimal("5000.00")
        assert payment.payment_type == PaymentTypeCode.USER_MEMBERSHIP_FEE
        # MEMBERSHIP flows user -> club.
        assert payment.sender_wallet_id == user.w_id
        assert payment.receiver_wallet_id == company.w_id

    def test_monthly_membership_is_idempotent(
        self, db_session, monthly_membership_contract
    ):
        _, _, contract = monthly_membership_contract()
        _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1))

        second = _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1))

        assert second == 0
        assert len(_periods(db_session, contract)) == 1

    def test_monthly_membership_rolls_forward(
        self, db_session, monthly_membership_contract
    ):
        """Open-ended: every run adds the month it is asked for, with no end
        in sight. This is what replaced re-signing each term."""
        _, _, contract = monthly_membership_contract()

        for month in (1, 2, 3):
            _monthly_recurring_billing_job(db_session, on_date=date(2026, month, 1))

        assert _periods(db_session, contract) == [
            (date(2026, 1, 1), date(2026, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
            (date(2026, 3, 1), date(2026, 3, 31)),
        ]

    def test_term_membership_is_never_touched(
        self, db_session, create_company, create_user, freeze_club_today
    ):
        """A TERM block is billed once at signing; the job must not renew it."""
        freeze_club_today(date(2026, 1, 15))
        company = create_company(name="Club")
        company.w_id = _wallet_for(
            db_session, company.id, WalletOwnerType.COMPANY, "Club"
        ).id
        user = create_user(company_id=company.id)
        user.w_id = _wallet_for(
            db_session, user.id, WalletOwnerType.USER, "Player"
        ).id
        db_session.commit()

        plan = _plan(
            db_session, company, _selection(db_session, company.id, "Masters"),
            billing_type=BillingType.TERM, price=Decimal("15000.00"), term_months=3,
        )
        contract = ContractService(db_session).create(ContractCreate(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.MEMBERSHIP,
            membership_id=plan.id,
            start_date=date(2026, 1, 1),
        ))
        before = _periods(db_session, contract)
        assert before == [(date(2026, 1, 1), date(2026, 3, 31))]

        _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1))

        assert _periods(db_session, contract) == before

    def test_missing_wallet_keeps_the_month_for_the_nightly_job(
        self, db_session, staff_contract
    ):
        """No payment can be raised, but the month is still owed — the nightly
        job bills it once the wallet exists."""
        _, user, contract = staff_contract(with_user_wallet=False)

        _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1))

        assert _periods(db_session, contract) == [
            (date(2026, 2, 1), date(2026, 2, 28)),
        ]
        assert _installment_payments(db_session) == []

        user.w_id = _wallet_for(db_session, user.id, WalletOwnerType.USER, "Coach").id
        db_session.commit()

        assert _nightly_billing_job(db_session, on_date=date(2026, 2, 2)) == 1


@pytest.fixture()
def billed_membership(db_session, create_company, create_user):
    """An ACTIVE MONTHLY contract signed mid-January: one installment for the
    current month, and its PENDING payment raised on the spot."""
    def _create():
        company = create_company(name="Club")
        company.w_id = _wallet_for(
            db_session, company.id, WalletOwnerType.COMPANY, "Club"
        ).id
        user = create_user(company_id=company.id)
        user.w_id = _wallet_for(
            db_session, user.id, WalletOwnerType.USER, "Player"
        ).id
        db_session.commit()

        plan = _plan(db_session, company, _selection(db_session, company.id))
        contract = ContractService(db_session).create(ContractCreate(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.MEMBERSHIP,
            membership_id=plan.id,
            start_date=date(2026, 1, 1),
        ))
        return company, user, contract
    return _create


class TestDailyDebtJob:
    """PENDING -> DEBT once a due date has passed.

    DEBT changes nothing about the money — it is still owed and still counts in
    a wallet's outstanding totals. It only marks the due as late.
    """

    def test_past_due_becomes_debt(self, db_session, billed_membership):
        billed_membership()  # due 2026-01-01
        [payment] = _installment_payments(db_session)
        assert payment.status == PaymentStatus.PENDING

        moved = _daily_debt_job(db_session, on_date=date(2026, 2, 1))

        assert moved == 1
        db_session.refresh(payment)
        assert payment.status == PaymentStatus.DEBT

    def test_a_due_not_yet_past_is_left_pending(self, db_session, billed_membership):
        billed_membership()  # due 2026-01-01

        # On the due date itself nothing is late yet.
        assert _daily_debt_job(db_session, on_date=date(2026, 1, 1)) == 0
        [payment] = _installment_payments(db_session)
        assert payment.status == PaymentStatus.PENDING

    def test_is_idempotent(self, db_session, billed_membership):
        billed_membership()
        _daily_debt_job(db_session, on_date=date(2026, 2, 1))

        assert _daily_debt_job(db_session, on_date=date(2026, 2, 1)) == 0
        [payment] = _installment_payments(db_session)
        assert payment.status == PaymentStatus.DEBT

    def test_settled_dues_are_untouched(self, db_session, billed_membership):
        billed_membership()
        [payment] = _installment_payments(db_session)
        payment.status = PaymentStatus.COMPLETED
        db_session.commit()

        assert _daily_debt_job(db_session, on_date=date(2026, 2, 1)) == 0
        db_session.refresh(payment)
        assert payment.status == PaymentStatus.COMPLETED

    def test_waived_installments_are_skipped(self, db_session, billed_membership):
        """Waiving settles the period by decision, so it is not a debt."""
        _, _, contract = billed_membership()
        [row] = db_session.query(ContractInstallment).filter(
            ContractInstallment.contract_id == contract.id
        ).all()
        # Waiving drops the unpaid payment outright, so re-raise one to prove
        # the job filters on `waived` rather than on the payment being gone.
        row.waived = True
        db_session.commit()

        assert _daily_debt_job(db_session, on_date=date(2026, 2, 1)) == 0

    def test_payables_without_a_due_date_are_never_swept(
        self, db_session, create_company, create_user
    ):
        """Only contract instalments have a due date; a training payment must
        not be dragged into the sweep by the join."""
        company = create_company(name="Club")
        user = create_user(company_id=company.id)
        sender = _wallet_for(db_session, user.id, WalletOwnerType.USER, "Player")
        receiver = _wallet_for(db_session, company.id, WalletOwnerType.COMPANY, "Club")
        payment = Payment(
            sender_wallet_id=sender.id,
            receiver_wallet_id=receiver.id,
            payment_type=PaymentTypeCode.USER_MEMBERSHIP_FEE,
            amount=Decimal("100.00"),
            status=PaymentStatus.PENDING,
            payable_type=PayableType.TRAINING,
            payable_id=1,
        )
        db_session.add(payment)
        db_session.commit()

        assert _daily_debt_job(db_session, on_date=date(2026, 12, 31)) == 0
        db_session.refresh(payment)
        assert payment.status == PaymentStatus.PENDING

    def test_debt_still_counts_as_outstanding_on_the_wallet(
        self, db_session, billed_membership
    ):
        """The headline risk: an overdue due must not fall out of the club's
        outstanding total just because it went late."""
        from app.features.wallet.wallet_service import WalletService

        company, _, _ = billed_membership()
        before = WalletService(db_session).get_summary(company.w_id)
        assert before["total_in_pending"] == Decimal("5000.00")

        _daily_debt_job(db_session, on_date=date(2026, 2, 1))

        after = WalletService(db_session).get_summary(company.w_id)
        assert after["total_in_pending"] == Decimal("5000.00")

    def test_installment_reports_debt(self, db_session, billed_membership):
        """The computed payment_status reads the flag off the payment, so
        lateness is decided in exactly one place."""
        _, _, contract = billed_membership()
        service = ContractInstallmentService(db_session)
        [row] = db_session.query(ContractInstallment).filter(
            ContractInstallment.contract_id == contract.id
        ).all()
        assert service.get_by_id(row.id).payment_status == "pending"

        _daily_debt_job(db_session, on_date=date(2026, 2, 1))

        assert service.get_by_id(row.id).payment_status == "debt"

    def test_a_partially_paid_debt_still_reports_partial(
        self, db_session, billed_membership
    ):
        """How much is outstanding is the more useful fact than lateness."""
        company, user, contract = billed_membership()
        service = ContractInstallmentService(db_session)
        [row] = db_session.query(ContractInstallment).filter(
            ContractInstallment.contract_id == contract.id
        ).all()
        _daily_debt_job(db_session, on_date=date(2026, 2, 1))

        db_session.add(Payment(
            sender_wallet_id=user.w_id,
            receiver_wallet_id=company.w_id,
            payment_type=PaymentTypeCode.USER_MEMBERSHIP_FEE,
            amount=Decimal("2000.00"),
            status=PaymentStatus.COMPLETED,
            payable_type=PayableType.CONTRACT_INSTALLMENT,
            payable_id=row.id,
        ))
        db_session.commit()

        assert service.get_by_id(row.id).payment_status == "partial"

    def test_waiving_clears_an_overdue_due(self, db_session, billed_membership):
        """The waive path drops unsettled money — DEBT is unsettled too."""
        _, _, contract = billed_membership()
        [row] = db_session.query(ContractInstallment).filter(
            ContractInstallment.contract_id == contract.id
        ).all()
        _daily_debt_job(db_session, on_date=date(2026, 2, 1))
        assert len(_installment_payments(db_session)) == 1

        ContractInstallmentService(db_session).waive(row.id)

        assert _installment_payments(db_session) == []


class TestInstallmentPaymentStatus:

    def test_status_is_computed_from_payments(self, db_session, billed_membership):
        company, user, contract = billed_membership()
        service = ContractInstallmentService(db_session)

        installment = (
            db_session.query(ContractInstallment)
            .filter(ContractInstallment.contract_id == contract.id)
            .order_by(ContractInstallment.period_start)
            .first()
        )

        # Only COMPLETED payments count, so the PENDING one raised at signing
        # leaves the row owing its full amount.
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

    def test_waived_short_circuits_status(self, db_session, billed_membership):
        company, user, contract = billed_membership()
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
        user.w_id = sender.id
        company.w_id = receiver.id
        db_session.commit()

        plan = _plan(db_session, company, _selection(db_session, company.id))
        contract = ContractService(db_session).create(ContractCreate(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.MEMBERSHIP,
            membership_id=plan.id,
            start_date=date(2026, 1, 1),
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
