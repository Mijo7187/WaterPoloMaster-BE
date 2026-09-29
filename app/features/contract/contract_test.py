# ============================================
# CONTRACT TESTS
# ============================================

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.core.api.exceptions import (
    BadRequestException,
    NotFoundException,
    ValidationException,
)
from app.features.contract.contract_model import Contract, ContractStatus, ContractType
from app.features.contract.contract_repository import ContractRepository
from app.features.contract.contract_schemas import (
    ContractCreate,
    ContractFilters,
    ContractResponse,
    ContractUpdate,
)
from app.features.contract.contract_service import (
    ContractService,
    compute_contract_status,
    month_bounds,
    term_end_date,
)
from app.features.contract_installment.contract_installment_model import (
    ContractInstallment,
)
from app.features.contract_installment.contract_installment_schemas import (
    ContractInstallmentUpdate,
)
from app.features.contract_installment.contract_installment_service import (
    ContractInstallmentService,
)
from app.features.group.group_model import Group
from app.features.group_user.group_user_model import GroupUser
from app.features.membership.membership_model import BillingType, Program
from app.features.membership.membership_schemas import (
    MembershipCreate,
    MembershipUpdate,
)
from app.features.membership.membership_service import MembershipService
from app.features.payment.payment_model import (
    PayableType,
    Payment,
    PaymentStatus,
    PaymentTypeCode,
)
from app.features.season.season_model import Season
from app.features.sifarnici.selection.selection_model import Selection
from app.features.wallet.wallet_model import Wallet, WalletOwnerType
from app.scheduler.contract_jobs import _daily_contract_status_job

# Most tests run "on" this day: a contract starting 2026-01-01 is ACTIVE.
TODAY = date(2026, 1, 15)
START = date(2026, 1, 1)


@pytest.fixture(autouse=True)
def _today(freeze_club_today):
    freeze_club_today(TODAY)


def _installments(db_session, contract):
    return (
        db_session.query(ContractInstallment)
        .filter(ContractInstallment.contract_id == contract.id)
        .order_by(ContractInstallment.period_start)
        .all()
    )


def _payments(db_session):
    return (
        db_session.query(Payment)
        .filter(Payment.payable_type == PayableType.CONTRACT_INSTALLMENT)
        .all()
    )


def _selection(db_session, company_id, name="U15"):
    selection = Selection(company_id=company_id, name=name)
    db_session.add(selection)
    db_session.commit()
    db_session.refresh(selection)
    return selection


def _plan(db_session, company, selection=None, **kwargs):
    """A catalog plan. Defaults to MONTHLY at 5000."""
    if selection is None:
        selection = _selection(db_session, company.id, name=f"S{company.id}")
    payload = dict(
        company_id=company.id,
        selection_id=selection.id,
        name="Senior Waterpolo",
        program=Program.WATERPOLO,
        billing_type=BillingType.MONTHLY,
        price=Decimal("5000.00"),
    )
    payload.update(kwargs)
    return MembershipService(db_session).create(MembershipCreate(**payload))


def _term_plan(db_session, company, selection=None, **kwargs):
    """A Masters-style block: 3 months for 15000."""
    payload = dict(
        billing_type=BillingType.TERM,
        price=Decimal("15000.00"),
        term_months=3,
        name="Masters",
    )
    payload.update(kwargs)
    return _plan(db_session, company, selection, **payload)


def _membership(db_session, company, user, plan=None, **kwargs):
    """A MEMBERSHIP contract signed off a plan. Defaults to MONTHLY from Jan 1."""
    if plan is None:
        plan = _plan(db_session, company)
    payload = dict(
        company_id=company.id,
        user_id=user.id,
        contract_type=ContractType.MEMBERSHIP,
        membership_id=plan.id,
        start_date=START,
    )
    payload.update(kwargs)
    return ContractService(db_session).create(ContractCreate(**payload))


def _staff(db_session, company, user, **kwargs):
    payload = dict(
        company_id=company.id,
        user_id=user.id,
        contract_type=ContractType.STAFF,
        amount=Decimal("120000.00"),
        start_date=START,
    )
    payload.update(kwargs)
    return ContractService(db_session).create(ContractCreate(**payload))


def _locs(exc_info):
    return [e["loc"] for e in exc_info.value.field_errors]


def _wallet(db_session, owner_id, owner_type, name):
    wallet = Wallet(owner_id=owner_id, owner_type=owner_type, name=name)
    db_session.add(wallet)
    db_session.commit()
    db_session.refresh(wallet)
    return wallet


@pytest.fixture()
def parties(db_session, create_company, create_user):
    """A club and a player, each with a wallet (either can be left out)."""
    def _create(company_wallet=True, user_wallet=True):
        company = create_company(name="Wallet Club")
        if company_wallet:
            company.w_id = _wallet(
                db_session, company.id, WalletOwnerType.COMPANY, "Club"
            ).id
        user = create_user(company_id=company.id)
        if user_wallet:
            user.w_id = _wallet(db_session, user.id, WalletOwnerType.USER, "Player").id
        db_session.commit()
        return company, user
    return _create


# ============================================
# Pure helpers
# ============================================

class TestComputeContractStatus:
    D = date(2026, 5, 10)

    def test_future_start_is_draft(self):
        assert compute_contract_status(self.D.replace(day=11), None, self.D) == ContractStatus.DRAFT

    def test_started_without_end_date_is_active(self):
        assert compute_contract_status(date(2026, 4, 10), None, self.D) == ContractStatus.ACTIVE

    def test_started_and_not_yet_ended_is_active(self):
        assert compute_contract_status(
            date(2026, 4, 10), date(2026, 6, 9), self.D
        ) == ContractStatus.ACTIVE

    def test_both_dates_before_today_is_ended(self):
        assert compute_contract_status(
            date(2026, 4, 10), date(2026, 5, 9), self.D
        ) == ContractStatus.ENDED

    def test_start_equal_today_is_active(self):
        assert compute_contract_status(self.D, None, self.D) == ContractStatus.ACTIVE

    def test_end_equal_today_is_still_active(self):
        assert compute_contract_status(
            date(2026, 4, 10), self.D, self.D
        ) == ContractStatus.ACTIVE

    def test_start_and_end_today_is_active(self):
        assert compute_contract_status(self.D, self.D, self.D) == ContractStatus.ACTIVE

    def test_cancelled_is_sticky(self):
        assert compute_contract_status(
            date(2026, 4, 10), None, self.D, ContractStatus.CANCELLED
        ) == ContractStatus.CANCELLED

    def test_cancelled_is_sticky_even_when_ended(self):
        assert compute_contract_status(
            date(2026, 4, 10), date(2026, 5, 9), self.D, ContractStatus.CANCELLED
        ) == ContractStatus.CANCELLED


class TestMonthBounds:

    def test_is_the_calendar_month(self):
        assert month_bounds(date(2026, 2, 17)) == (date(2026, 2, 1), date(2026, 2, 28))

    def test_leap_february(self):
        assert month_bounds(date(2028, 2, 1)) == (date(2028, 2, 1), date(2028, 2, 29))


class TestTermEndDate:
    """A TERM block's last day is inclusive: 3 months from Sep 1 ends Nov 30."""

    def test_three_months(self):
        assert term_end_date(date(2026, 9, 1), 3) == date(2026, 11, 30)

    def test_one_month(self):
        assert term_end_date(date(2026, 1, 1), 1) == date(2026, 1, 31)

    def test_day_is_clamped_to_the_target_month(self):
        assert term_end_date(date(2026, 1, 31), 1) == date(2026, 2, 27)


# ============================================
# MEMBERSHIP MONTHLY create — open-ended
# ============================================

class TestMembershipMonthlyCreate:

    def test_is_open_ended_and_owes_the_current_month(self, db_session, parties):
        company, user = parties()

        contract = _membership(db_session, company, user)

        # Open-ended: there is no end date to re-sign against.
        assert contract.end_date is None
        assert contract.status == ContractStatus.ACTIVE
        assert contract.billing_type == BillingType.MONTHLY
        assert contract.term_months is None
        # amount is the PER-INSTALLMENT price, not a term total.
        assert contract.amount == Decimal("5000.00")

        rows = _installments(db_session, contract)
        assert [(i.period_start, i.period_end, i.due_date, i.amount) for i in rows] == [
            (date(2026, 1, 1), date(2026, 1, 31), date(2026, 1, 1), Decimal("5000.00")),
        ]

    def test_payment_is_raised_on_the_spot(self, db_session, parties):
        """Signing a contract bills it immediately — the player sees the charge
        without waiting for the nightly sweep."""
        company, user = parties()

        contract = _membership(db_session, company, user)

        [payment] = _payments(db_session)
        assert payment.status == PaymentStatus.PENDING
        assert payment.payment_type == PaymentTypeCode.USER_MEMBERSHIP_FEE
        assert payment.amount == Decimal("5000.00")
        # MEMBERSHIP flows user -> club.
        assert payment.sender_wallet_id == user.w_id
        assert payment.receiver_wallet_id == company.w_id
        assert payment.payable_id == _installments(db_session, contract)[0].id

    def test_re_running_generation_adds_nothing(self, db_session, parties):
        """UNIQUE(contract_id, period_start) makes it idempotent."""
        from app.scheduler.billing_jobs import _monthly_recurring_billing_job

        company, user = parties()
        contract = _membership(db_session, company, user)

        assert _monthly_recurring_billing_job(db_session, on_date=TODAY) == 0
        assert len(_installments(db_session, contract)) == 1
        assert len(_payments(db_session)) == 1

    def test_the_next_month_adds_one_more(self, db_session, parties):
        from app.scheduler.billing_jobs import _monthly_recurring_billing_job

        company, user = parties()
        contract = _membership(db_session, company, user)

        assert _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1)) == 1
        assert [i.period_start for i in _installments(db_session, contract)] == [
            date(2026, 1, 1), date(2026, 2, 1),
        ]

    def test_future_start_is_draft_with_no_installments(self, db_session, parties):
        company, user = parties()

        contract = _membership(
            db_session, company, user, start_date=date(2026, 3, 1)
        )

        assert contract.status == ContractStatus.DRAFT
        assert _installments(db_session, contract) == []

    def test_a_missing_wallet_still_writes_the_period(self, db_session, parties):
        """post_create runs after the row is committed, so a failure to raise the
        payment must not fail the contract. The nightly job bills it later."""
        company, user = parties(user_wallet=False)

        contract = _membership(db_session, company, user)

        assert contract.status == ContractStatus.ACTIVE
        assert len(_installments(db_session, contract)) == 1
        assert _payments(db_session) == []

    def test_response_includes_the_installments(self, db_session, parties):
        company, user = parties()
        contract = _membership(db_session, company, user)

        dumped = ContractResponse.model_validate(contract).model_dump()
        assert len(dumped["installments"]) == 1
        assert dumped["billing_type"] == BillingType.MONTHLY


# ============================================
# MEMBERSHIP TERM create — one fixed block
# ============================================

class TestMembershipTermCreate:

    def test_end_date_is_derived_and_one_block_is_written(self, db_session, parties):
        company, user = parties()
        plan = _term_plan(db_session, company)

        contract = _membership(db_session, company, user, plan)

        assert contract.billing_type == BillingType.TERM
        assert contract.term_months == 3
        assert contract.amount == Decimal("15000.00")
        assert contract.end_date == date(2026, 3, 31)

        rows = _installments(db_session, contract)
        assert [(i.period_start, i.period_end, i.due_date, i.amount) for i in rows] == [
            (date(2026, 1, 1), date(2026, 3, 31), date(2026, 1, 1), Decimal("15000.00")),
        ]

    def test_the_block_is_billed_once(self, db_session, parties):
        company, user = parties()
        plan = _term_plan(db_session, company)

        _membership(db_session, company, user, plan)

        [payment] = _payments(db_session)
        assert payment.amount == Decimal("15000.00")

    def test_the_recurring_job_never_renews_it(self, db_session, parties):
        from app.scheduler.billing_jobs import _monthly_recurring_billing_job

        company, user = parties()
        contract = _membership(db_session, company, user, _term_plan(db_session, company))
        before = _installments(db_session, contract)

        _monthly_recurring_billing_job(db_session, on_date=date(2026, 2, 1))

        assert len(_installments(db_session, contract)) == len(before) == 1

    def test_a_contradicting_end_date_is_422(self, db_session, parties):
        company, user = parties()
        plan = _term_plan(db_session, company)

        with pytest.raises(ValidationException) as exc:
            _membership(
                db_session, company, user, plan, end_date=date(2026, 6, 30)
            )
        assert _locs(exc) == [["end_date"]]

    def test_the_derived_end_date_may_be_echoed_back(self, db_session, parties):
        """The frontend may send back the (disabled) value it was shown."""
        company, user = parties()
        plan = _term_plan(db_session, company)

        contract = _membership(
            db_session, company, user, plan, end_date=date(2026, 3, 31)
        )
        assert contract.end_date == date(2026, 3, 31)

    def test_monthly_rejects_an_end_date(self, db_session, parties):
        company, user = parties()

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, end_date=date(2026, 6, 30))
        assert _locs(exc) == [["end_date"]]


# ============================================
# MEMBERSHIP create — validation
# ============================================

class TestMembershipCreateValidation:

    def test_membership_id_is_required(self, db_session, parties):
        """The plan IS the terms now — there is nothing to sign without one."""
        company, user = parties()

        with pytest.raises(ValidationException) as exc:
            ContractService(db_session).create(ContractCreate(
                company_id=company.id,
                user_id=user.id,
                contract_type=ContractType.MEMBERSHIP,
                start_date=START,
            ))
        assert _locs(exc) == [["membership_id"]]

    def test_start_date_is_required(self, db_session, parties):
        company, user = parties()
        plan = _plan(db_session, company)

        with pytest.raises(ValidationException) as exc:
            ContractService(db_session).create(ContractCreate(
                company_id=company.id,
                user_id=user.id,
                contract_type=ContractType.MEMBERSHIP,
                membership_id=plan.id,
            ))
        assert _locs(exc) == [["start_date"]]

    def test_a_plan_from_another_company_is_422(
        self, db_session, parties, create_company
    ):
        company, user = parties()
        other = create_company(name="Other Club")
        plan = _plan(db_session, other)

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, plan)
        assert _locs(exc) == [["membership_id"]]

    def test_a_plan_from_the_companys_academy_is_accepted(
        self, db_session, parties, create_company
    ):
        """The academy owns the shared catalog; the contract stays at the club."""
        company, user = parties()
        academy = create_company(name="Akademija")
        company.academy_id = academy.id
        db_session.commit()

        plan = _plan(db_session, academy, price=Decimal("7000.00"))
        contract = _membership(db_session, company, user, plan)

        assert contract.company_id == company.id
        assert contract.membership_id == plan.id
        assert Decimal(contract.amount) == Decimal("7000.00")

    def test_an_unknown_plan_is_404(self, db_session, parties):
        company, user = parties()

        with pytest.raises(NotFoundException):
            ContractService(db_session).create(ContractCreate(
                company_id=company.id,
                user_id=user.id,
                contract_type=ContractType.MEMBERSHIP,
                membership_id=9999,
                start_date=START,
            ))

    def test_client_status_is_ignored(self, db_session, parties):
        company, user = parties()
        contract = _membership(db_session, company, user, status=ContractStatus.ENDED)
        assert contract.status == ContractStatus.ACTIVE

    def test_cancelled_on_create_is_422(self, db_session, parties):
        company, user = parties()

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, status=ContractStatus.CANCELLED)
        assert _locs(exc) == [["status"]]

    def test_a_zero_priced_plan_is_never_billed(self, db_session, parties):
        """A scholarship needs no special flag — a 0 installment owes nothing."""
        from app.scheduler.billing_jobs import _nightly_billing_job

        company, user = parties()
        # price must be > 0 on the plan, so the scholarship is the waived row.
        contract = _membership(db_session, company, user)
        [row] = _installments(db_session, contract)
        ContractInstallmentService(db_session).waive(row.id)

        assert _nightly_billing_job(db_session, on_date=date(2026, 1, 31)) == 0
        assert _payments(db_session) == []


class TestValidationErrorShape:
    """422s carry field-level {loc, msg} the frontend can pin on a field."""

    def _post(self, client, headers, body):
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            return client.post("/api/contract/", headers=headers, json=body)

    def test_service_error_points_at_the_field(
        self, client, db_session, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)
        plan = _term_plan(db_session, company)

        r = self._post(client, headers, {
            "company_id": company.id,
            "user_id": user.id,
            "contract_type": "membership",
            "membership_id": plan.id,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        })

        assert r.status_code == 422, r.text
        assert ["end_date"] in [e["loc"] for e in r.json()["errors"]]

    def test_schema_error_uses_the_same_shape(
        self, client, db_session, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)

        r = self._post(client, headers, {
            "company_id": company.id,
            "user_id": user.id,
            "contract_type": "not-a-type",
            "start_date": "2026-01-01",
        })

        assert r.status_code == 422
        assert ["contract_type"] in [e["loc"] for e in r.json()["errors"]]

    def test_valid_request_creates_the_contract(
        self, client, db_session, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)
        plan = _plan(db_session, company)

        r = self._post(client, headers, {
            "company_id": company.id,
            "user_id": user.id,
            "contract_type": "membership",
            "membership_id": plan.id,
            "start_date": "2026-01-01",
        })

        assert r.status_code in (200, 201), r.text
        [contract_id] = r.json()["data"]
        contract = db_session.get(Contract, contract_id)
        assert contract.amount == Decimal("5000.00")
        assert contract.status == ContractStatus.ACTIVE


# ============================================
# The plan snapshot
# ============================================

class TestContractSnapshot:
    """billing_type / amount / term_months are copied at signing, then inert."""

    def test_terms_are_taken_from_the_plan(self, db_session, parties):
        company, user = parties()
        plan = _plan(db_session, company, price=Decimal("7500.00"))

        contract = _membership(db_session, company, user, plan)

        assert contract.membership_id == plan.id
        assert contract.amount == Decimal("7500.00")
        assert contract.billing_type == BillingType.MONTHLY

    def test_contract_does_not_follow_the_plan_after_signing(
        self, db_session, parties
    ):
        company, user = parties()
        plan = _plan(db_session, company)
        contract = _membership(db_session, company, user, plan)

        MembershipService(db_session).update(
            plan.id, MembershipUpdate(price=Decimal("9000.00"))
        )
        db_session.refresh(contract)

        assert contract.amount == Decimal("5000.00")

    def test_the_nested_membership_carries_its_selection(
        self, client, db_session, create_user, auth_headers
    ):
        """`membership.selection` survives both contract read paths — the list
        and the detail — so the UI can name the squad without another call."""
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)
        selection = _selection(db_session, company.id, "U15")
        contract = _membership(
            db_session, company, user, _plan(db_session, company, selection)
        )

        listed = _call(client, "get", "/api/contract/", headers)
        assert listed.status_code == 200
        [row] = [i for i in listed.json()["data"]["items"] if i["id"] == contract.id]
        assert row["membership"]["selection"]["name"] == "U15"

        one = _call(client, "get", f"/api/contract/{contract.id}", headers)
        assert one.status_code == 200
        assert one.json()["data"]["membership"]["selection"]["id"] == selection.id

    def test_retiring_the_plan_does_not_move_the_contract(self, db_session, parties):
        company, user = parties()
        plan = _plan(db_session, company)
        contract = _membership(db_session, company, user, plan)

        MembershipService(db_session).update(plan.id, MembershipUpdate(is_active=False))
        db_session.refresh(contract)

        assert contract.status == ContractStatus.ACTIVE
        assert contract.amount == Decimal("5000.00")


# ============================================
# STAFF create
# ============================================

class TestStaffCreate:

    def test_status_is_computed_and_the_current_month_is_added(
        self, db_session, parties
    ):
        company, user = parties()

        contract = _staff(db_session, company, user)

        assert contract.status == ContractStatus.ACTIVE
        [row] = _installments(db_session, contract)
        assert (row.period_start, row.period_end) == month_bounds(TODAY)
        assert row.amount == Decimal("120000.00")

    def test_future_start_is_draft_with_no_installments(self, db_session, parties):
        company, user = parties()

        contract = _staff(db_session, company, user, start_date=date(2026, 3, 1))

        assert contract.status == ContractStatus.DRAFT
        assert _installments(db_session, contract) == []

    def test_membership_id_is_422(self, db_session, parties):
        company, user = parties()
        plan = _plan(db_session, company)

        with pytest.raises(ValidationException) as exc:
            _staff(db_session, company, user, membership_id=plan.id)
        assert _locs(exc) == [["membership_id"]]

    @pytest.mark.parametrize("amount", [None, Decimal("0")])
    def test_amount_is_required_and_positive(self, db_session, parties, amount):
        company, user = parties()

        with pytest.raises(ValidationException) as exc:
            _staff(db_session, company, user, amount=amount)
        assert _locs(exc) == [["amount"]]

    def test_end_before_start_is_422(self, db_session, parties):
        company, user = parties()

        with pytest.raises(ValidationException) as exc:
            _staff(db_session, company, user, end_date=date(2025, 12, 31))
        assert _locs(exc) == [["end_date"]]


# ============================================
# Update
# ============================================

class TestContractUpdate:

    def test_client_active_or_ended_is_overwritten(self, db_session, parties):
        company, user = parties()
        service = ContractService(db_session)
        active = _membership(db_session, company, user)
        draft = _staff(db_session, company, user, start_date=date(2026, 6, 1))

        assert service.update(
            active.id, ContractUpdate(status=ContractStatus.ENDED)
        ).status == ContractStatus.ACTIVE
        assert service.update(
            draft.id, ContractUpdate(status=ContractStatus.ACTIVE)
        ).status == ContractStatus.DRAFT

    def test_cancelled_is_accepted_and_sticky(
        self, db_session, parties, freeze_club_today
    ):
        company, user = parties()
        service = ContractService(db_session)
        contract = _staff(db_session, company, user, start_date=date(2026, 6, 1))

        assert service.update(
            contract.id, ContractUpdate(status=ContractStatus.CANCELLED)
        ).status == ContractStatus.CANCELLED
        assert service.update(
            contract.id, ContractUpdate(status=ContractStatus.ACTIVE)
        ).status == ContractStatus.CANCELLED
        assert service.update(
            contract.id, ContractUpdate(amount=Decimal("1000.00"))
        ).status == ContractStatus.CANCELLED

        # Neither /activate nor the passage of time un-cancels it.
        freeze_club_today(date(2026, 7, 1))
        assert service.activate(contract.id).status == ContractStatus.CANCELLED
        assert _installments(db_session, contract) == []

    def test_setting_an_end_date_closes_an_open_ended_contract(
        self, db_session, parties
    ):
        """This is how a MONTHLY membership is stopped — there is no term to
        run out, so the club sets the last day."""
        company, user = parties()
        contract = _membership(db_session, company, user)
        assert contract.end_date is None

        updated = ContractService(db_session).update(
            contract.id, ContractUpdate(end_date=date(2026, 1, 10))
        )

        assert updated.end_date == date(2026, 1, 10)
        assert updated.status == ContractStatus.ENDED

    def test_membership_amount_is_freely_settable(self, db_session, parties):
        """It is the per-installment price now, not a sum to be matched."""
        company, user = parties()
        contract = _membership(db_session, company, user)

        updated = ContractService(db_session).update(
            contract.id, ContractUpdate(amount=Decimal("6000.00"))
        )
        assert updated.amount == Decimal("6000.00")

    def test_amount_must_stay_positive(self, db_session, parties):
        company, user = parties()
        contract = _membership(db_session, company, user)

        with pytest.raises(ValidationException) as exc:
            ContractService(db_session).update(
                contract.id, ContractUpdate(amount=Decimal("0"))
            )
        assert _locs(exc) == [["amount"]]

    def test_staff_end_date_change_recomputes_status(self, db_session, parties):
        company, user = parties()
        contract = _staff(db_session, company, user)

        updated = ContractService(db_session).update(
            contract.id, ContractUpdate(end_date=date(2026, 1, 10))
        )
        assert updated.status == ContractStatus.ENDED

    def test_staff_amount_and_end_date_are_updatable(self, db_session, parties):
        company, user = parties()
        contract = _staff(db_session, company, user)

        updated = ContractService(db_session).update(contract.id, ContractUpdate(
            amount=Decimal("130000.00"), end_date=date(2026, 12, 31)
        ))
        assert updated.amount == Decimal("130000.00")
        assert updated.end_date == date(2026, 12, 31)
        assert updated.status == ContractStatus.ACTIVE

    def test_end_before_start_is_422(self, db_session, parties):
        company, user = parties()
        contract = _staff(db_session, company, user)

        with pytest.raises(ValidationException) as exc:
            ContractService(db_session).update(
                contract.id, ContractUpdate(end_date=date(2025, 12, 1))
            )
        assert _locs(exc) == [["end_date"]]


class TestInstallmentEditDoesNotResync:
    """Editing one period is a local correction.

    Under Model A `contract.amount` WAS the sum of its installments, so a row
    edit re-derived the contract. It is now the per-installment price and the
    dates are the contract's own, so that re-derivation would be wrong.
    """

    def test_amount_edit_leaves_the_contract_alone(self, db_session, parties):
        company, user = parties()
        contract = _membership(db_session, company, user)
        [first] = _installments(db_session, contract)

        ContractInstallmentService(db_session).update(
            first.id, ContractInstallmentUpdate(amount=Decimal("4000.00"))
        )

        db_session.refresh(contract)
        assert contract.amount == Decimal("5000.00")

    def test_period_edit_leaves_the_dates_alone(self, db_session, parties):
        company, user = parties()
        contract = _membership(db_session, company, user)
        [first] = _installments(db_session, contract)

        ContractInstallmentService(db_session).update(
            first.id, ContractInstallmentUpdate(period_end=date(2026, 4, 30))
        )

        db_session.refresh(contract)
        assert contract.start_date == START
        assert contract.end_date is None

    def test_deleting_a_row_leaves_the_contract_alone(self, db_session, parties):
        company, user = parties()
        contract = _membership(db_session, company, user)
        [first] = _installments(db_session, contract)

        ContractInstallmentService(db_session).delete(first.id)

        db_session.refresh(contract)
        assert contract.amount == Decimal("5000.00")
        assert contract.end_date is None
        assert _installments(db_session, contract) == []

    def test_staff_contract_is_not_resynced_either(self, db_session, parties):
        company, user = parties()
        contract = _staff(db_session, company, user)
        [row] = _installments(db_session, contract)

        ContractInstallmentService(db_session).update(
            row.id, ContractInstallmentUpdate(amount=Decimal("100.00"))
        )

        db_session.refresh(contract)
        assert contract.amount == Decimal("120000.00")


# ============================================
# /activate — manual status refresh
# ============================================

class TestActivateRefreshesStatus:

    def test_generation_is_idempotent(self, db_session, parties):
        company, user = parties()
        contract = _membership(db_session, company, user)

        ContractService(db_session).activate(contract.id)
        ContractService(db_session).activate(contract.id)

        assert len(_installments(db_session, contract)) == 1

    def test_moves_a_stale_draft_to_active_and_generates(
        self, db_session, parties, freeze_club_today
    ):
        company, user = parties()
        contract = _membership(db_session, company, user, start_date=date(2026, 2, 1))
        assert contract.status == ContractStatus.DRAFT
        assert _installments(db_session, contract) == []

        freeze_club_today(date(2026, 2, 3))
        refreshed = ContractService(db_session).activate(contract.id)

        assert refreshed.status == ContractStatus.ACTIVE
        # Activation owes the current period straight away.
        [row] = _installments(db_session, contract)
        assert row.period_start == date(2026, 2, 1)

    def test_staff_draft_activates_and_generates(
        self, db_session, parties, freeze_club_today
    ):
        company, user = parties()
        contract = _staff(db_session, company, user, start_date=date(2026, 2, 1))

        freeze_club_today(date(2026, 2, 3))
        refreshed = ContractService(db_session).activate(contract.id)

        assert refreshed.status == ContractStatus.ACTIVE
        [row] = _installments(db_session, contract)
        assert row.period_start == date(2026, 2, 1)


# ============================================
# Daily status job
# ============================================

class TestDailyContractStatusJob:

    def test_moves_draft_to_active(self, db_session, parties):
        company, user = parties()
        contract = _staff(db_session, company, user, start_date=date(2026, 2, 1))

        assert _daily_contract_status_job(db_session, on_date=date(2026, 1, 31)) == 0
        assert _daily_contract_status_job(db_session, on_date=date(2026, 2, 1)) == 1

        db_session.refresh(contract)
        assert contract.status == ContractStatus.ACTIVE
        assert [i.period_start for i in _installments(db_session, contract)] == [
            date(2026, 2, 1)
        ]

    def test_moves_a_term_contract_to_ended(self, db_session, parties):
        """Only a dated contract can end by itself; MONTHLY is open-ended."""
        company, user = parties()
        contract = _membership(db_session, company, user, _term_plan(db_session, company))

        # end_date 2026-03-31 is still "today or later" on the 31st.
        assert _daily_contract_status_job(db_session, on_date=date(2026, 3, 31)) == 0
        assert _daily_contract_status_job(db_session, on_date=date(2026, 4, 1)) == 1

        db_session.refresh(contract)
        assert contract.status == ContractStatus.ENDED

    def test_ending_bills_what_was_never_billed(self, db_session, parties):
        """The block could not be billed at signing (no wallet); ending settles
        it once the wallet exists."""
        company, user = parties(user_wallet=False)
        contract = _membership(db_session, company, user, _term_plan(db_session, company))
        assert _payments(db_session) == []

        user.w_id = _wallet(db_session, user.id, WalletOwnerType.USER, "Player").id
        db_session.commit()

        assert _daily_contract_status_job(db_session, on_date=date(2026, 4, 1)) == 1

        db_session.refresh(contract)
        assert contract.status == ContractStatus.ENDED
        [payment] = _payments(db_session)
        assert payment.status == PaymentStatus.PENDING
        assert payment.payment_type == PaymentTypeCode.USER_MEMBERSHIP_FEE
        assert payment.sender_wallet_id == user.w_id
        assert payment.receiver_wallet_id == company.w_id

    def test_leaves_cancelled_alone(self, db_session, parties):
        company, user = parties()
        contract = _staff(db_session, company, user, start_date=date(2026, 2, 1))
        ContractService(db_session).update(
            contract.id, ContractUpdate(status=ContractStatus.CANCELLED)
        )

        assert _daily_contract_status_job(db_session, on_date=date(2026, 5, 1)) == 0

        db_session.refresh(contract)
        assert contract.status == ContractStatus.CANCELLED

    def test_is_idempotent(self, db_session, parties):
        company, user = parties()
        _membership(db_session, company, user, _term_plan(db_session, company))
        _daily_contract_status_job(db_session, on_date=date(2026, 4, 1))

        assert _daily_contract_status_job(db_session, on_date=date(2026, 4, 1)) == 0
        assert len(_payments(db_session)) == 1

    def test_missing_wallet_keeps_it_active_for_a_retry(self, db_session, parties):
        company, user = parties(user_wallet=False)
        contract = _membership(db_session, company, user, _term_plan(db_session, company))

        assert _daily_contract_status_job(db_session, on_date=date(2026, 4, 1)) == 0

        db_session.refresh(contract)
        assert contract.status == ContractStatus.ACTIVE
        assert _payments(db_session) == []


# ============================================
# Ending — settle whatever is left
# ============================================

class TestContractEndedBilling:

    def test_already_billed_installments_are_not_billed_twice(
        self, db_session, parties
    ):
        company, user = parties()
        _membership(db_session, company, user, _term_plan(db_session, company))
        assert len(_payments(db_session)) == 1

        _daily_contract_status_job(db_session, on_date=date(2026, 4, 1))

        payments = _payments(db_session)
        assert len(payments) == 1
        assert len({p.payable_id for p in payments}) == 1

    def test_waived_installment_is_not_billed(self, db_session, parties):
        company, user = parties(user_wallet=False)
        contract = _membership(db_session, company, user, _term_plan(db_session, company))
        [waived] = _installments(db_session, contract)
        ContractInstallmentService(db_session).waive(waived.id)

        user.w_id = _wallet(db_session, user.id, WalletOwnerType.USER, "Player").id
        db_session.commit()
        _daily_contract_status_job(db_session, on_date=date(2026, 4, 1))

        assert _payments(db_session) == []

    def test_backdated_term_contract_is_ended_and_billed_at_create(
        self, db_session, parties, freeze_club_today
    ):
        """A block signed after it finished is still owed."""
        company, user = parties()
        freeze_club_today(date(2026, 4, 1))

        contract = _membership(db_session, company, user, _term_plan(db_session, company))

        assert contract.status == ContractStatus.ENDED
        [payment] = _payments(db_session)
        assert payment.amount == Decimal("15000.00")

    def test_backdated_contract_without_wallet_is_refused(
        self, db_session, parties, freeze_club_today
    ):
        company, user = parties(user_wallet=False)
        freeze_club_today(date(2026, 4, 1))

        with pytest.raises(BadRequestException, match="no wallet"):
            _membership(db_session, company, user, _term_plan(db_session, company))

    def test_staff_ending_pays_the_user(self, db_session, parties):
        company, user = parties()
        contract = _staff(db_session, company, user)

        ContractService(db_session).update(
            contract.id, ContractUpdate(end_date=date(2026, 1, 10))
        )

        [payment] = _payments(db_session)
        assert payment.payment_type == PaymentTypeCode.CLUB_SALARY_USER
        assert payment.sender_wallet_id == company.w_id
        assert payment.receiver_wallet_id == user.w_id
        assert payment.amount == Decimal("120000.00")

    def test_ending_without_a_wallet_is_refused(self, db_session, parties):
        company, user = parties(user_wallet=False)
        contract = _staff(db_session, company, user)

        with pytest.raises(BadRequestException, match="no wallet"):
            ContractService(db_session).update(
                contract.id, ContractUpdate(end_date=date(2026, 1, 10))
            )

        db_session.refresh(contract)
        assert contract.status == ContractStatus.ACTIVE
        assert contract.end_date is None

    def test_re_saving_an_ended_contract_creates_no_duplicates(
        self, db_session, parties
    ):
        company, user = parties()
        contract = _membership(db_session, company, user, _term_plan(db_session, company))
        _daily_contract_status_job(db_session, on_date=date(2026, 4, 1))

        ContractService(db_session).update(
            contract.id, ContractUpdate(amount=Decimal("15000.00"))
        )

        assert len(_payments(db_session)) == 1


# ============================================
# Auto-enrol into the season's group
# ============================================

class TestAutoEnrolInGroup:
    """Signing a MEMBERSHIP contract puts the player in the current season's
    group — (season, membership.selection) — creating the group on first use."""

    def _roster(self, db_session):
        return [
            (gu.group.season_id, gu.group.selection_id, gu.user_id)
            for gu in db_session.query(GroupUser).all()
        ]

    def _season(self, db_session, company, is_current=True):
        season = Season(
            company_id=company.id,
            name="2025/26",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            is_current=is_current,
        )
        db_session.add(season)
        db_session.commit()
        db_session.refresh(season)
        return season

    def test_contract_create_enrols_the_user(self, db_session, parties):
        company, user = parties()
        season = self._season(db_session, company)
        selection = _selection(db_session, company.id, "U15")
        plan = _plan(db_session, company, selection)

        _membership(db_session, company, user, plan)

        assert self._roster(db_session) == [(season.id, selection.id, user.id)]

    def test_the_group_is_created_on_first_use(self, db_session, parties):
        company, user = parties()
        self._season(db_session, company)
        selection = _selection(db_session, company.id, "U15")
        assert db_session.query(Group).count() == 0

        _membership(db_session, company, user, _plan(db_session, company, selection))

        [group] = db_session.query(Group).all()
        assert group.selection_id == selection.id

    def test_a_second_player_joins_the_same_group(
        self, db_session, parties, create_user
    ):
        company, user = parties()
        self._season(db_session, company)
        selection = _selection(db_session, company.id, "U15")
        plan = _plan(db_session, company, selection)
        _membership(db_session, company, user, plan)

        second = create_user(
            email="second@test.com", username="second", company_id=company.id
        )
        _membership(db_session, company, second, plan)

        assert db_session.query(Group).count() == 1
        assert db_session.query(GroupUser).count() == 2

    def test_enrolment_is_idempotent(self, db_session, parties):
        company, user = parties()
        self._season(db_session, company)
        plan = _plan(db_session, company, _selection(db_session, company.id, "U15"))
        contract = _membership(db_session, company, user, plan)

        # post_update runs the same hook.
        ContractService(db_session).update(
            contract.id, ContractUpdate(amount=Decimal("5500.00"))
        )

        assert db_session.query(GroupUser).count() == 1

    def test_no_current_season_skips_without_failing(self, db_session, parties):
        company, user = parties()
        self._season(db_session, company, is_current=False)

        contract = _membership(db_session, company, user)

        assert contract.id is not None
        assert contract.status == ContractStatus.ACTIVE
        assert db_session.query(GroupUser).count() == 0

    def test_no_season_at_all_skips_without_failing(self, db_session, parties):
        company, user = parties()

        contract = _membership(db_session, company, user)

        assert contract.id is not None
        assert db_session.query(GroupUser).count() == 0

    def test_staff_contracts_are_not_enrolled(self, db_session, parties):
        company, user = parties()
        self._season(db_session, company)

        _staff(db_session, company, user)

        assert db_session.query(GroupUser).count() == 0

    def test_the_academys_season_is_used(self, db_session, parties, create_company):
        """Seasons live on the ACADEMY; selections and players on its clubs."""
        company, user = parties()
        academy = create_company(name="Academy")
        company.academy_id = academy.id
        db_session.commit()

        season = self._season(db_session, academy)
        selection = _selection(db_session, company.id, "U15")

        _membership(db_session, company, user, _plan(db_session, company, selection))

        assert self._roster(db_session) == [(season.id, selection.id, user.id)]


# ============================================
# ?season_id= filter
# ============================================

class TestSeasonMembersFilter:
    """`?season_id=` on the contract list = date overlap with the season.

    A contract is not pinned to a season at all — it carries its own
    start_date and end_date — so overlap is the only sensible reading,
    and it keeps the open-ended and multi-year contracts that the "Korisnici"
    tab has to show.
    """

    SEASON_START = date(2025, 9, 1)
    SEASON_END = date(2026, 6, 30)

    @pytest.fixture()
    def season_with_contracts(self, db_session, create_company, create_user):
        company = create_company(name="Overlap Club")
        season = Season(
            company_id=company.id,
            name="2025/26",
            start_date=self.SEASON_START,
            end_date=self.SEASON_END,
            is_current=True,
        )
        db_session.add(season)
        db_session.flush()

        def _contract(start, end, label):
            user = create_user(
                company_id=company.id,
                email=f"{label}@test.com",
                username=label,
            )
            row = Contract(
                company_id=company.id,
                user_id=user.id,
                contract_type=ContractType.STAFF,
                amount=Decimal("1000.00"),
                start_date=start,
                end_date=end,
                status=ContractStatus.ACTIVE,
            )
            db_session.add(row)
            db_session.flush()
            return row

        contracts = {
            "open_ended": _contract(date(2025, 9, 1), None, "open_ended"),
            "multi_year": _contract(date(2024, 1, 1), date(2027, 12, 31), "multi_year"),
            "ended_before": _contract(date(2024, 6, 1), date(2025, 6, 30), "ended_before"),
            "starts_after": _contract(date(2026, 9, 1), None, "starts_after"),
        }
        db_session.commit()
        return company, season, contracts

    def _ids(self, db_session, **kwargs):
        items, total = ContractRepository(db_session).get_list(
            ContractFilters(**kwargs)
        )
        return {c.id for c in items}, total

    def test_overlapping_contracts_are_returned(self, db_session, season_with_contracts):
        _, season, contracts = season_with_contracts
        ids, total = self._ids(db_session, season_id=season.id)

        assert contracts["open_ended"].id in ids
        assert contracts["multi_year"].id in ids
        assert total == 2

    def test_contract_ending_before_the_season_is_excluded(
        self, db_session, season_with_contracts
    ):
        _, season, contracts = season_with_contracts
        ids, _ = self._ids(db_session, season_id=season.id)
        assert contracts["ended_before"].id not in ids

    def test_contract_starting_after_the_season_is_excluded(
        self, db_session, season_with_contracts
    ):
        _, season, contracts = season_with_contracts
        ids, _ = self._ids(db_session, season_id=season.id)
        assert contracts["starts_after"].id not in ids

    def test_unknown_season_returns_an_empty_page_not_everything(
        self, db_session, season_with_contracts
    ):
        """The trap: a skipped filter returns an unfiltered list silently."""
        ids, total = self._ids(db_session, season_id=999999)
        assert ids == set()
        assert total == 0

    def test_other_filters_still_apply_alongside_season_id(
        self, db_session, season_with_contracts, create_user
    ):
        company, season, contracts = season_with_contracts
        ids, _ = self._ids(
            db_session, season_id=season.id, user_id=contracts["open_ended"].user_id
        )
        assert ids == {contracts["open_ended"].id}

    def test_pagination_still_applies(self, db_session, season_with_contracts):
        _, season, _ = season_with_contracts
        ids, total = self._ids(db_session, season_id=season.id, page=1, size=1)
        assert len(ids) == 1
        assert total == 2

    def test_an_open_ended_monthly_membership_matches(
        self, db_session, season_with_contracts, create_user
    ):
        """A MONTHLY contract has end_date NULL, so it belongs to every season
        from its start onward — which is the intended reading."""
        company, season, contracts = season_with_contracts
        user = create_user(
            company_id=company.id, email="member@test.com", username="member"
        )
        membership = Contract(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.MEMBERSHIP,
            billing_type=BillingType.MONTHLY,
            amount=Decimal("5000.00"),
            start_date=date(2025, 10, 1),
            end_date=None,
            status=ContractStatus.ACTIVE,
        )
        db_session.add(membership)
        db_session.commit()

        ids, _ = self._ids(db_session, season_id=season.id)
        assert membership.id in ids
        assert contracts["open_ended"].id in ids

        only_membership, _ = self._ids(
            db_session, season_id=season.id, contract_type=ContractType.MEMBERSHIP
        )
        assert only_membership == {membership.id}

    def test_endpoint_returns_a_filtered_paginated_list(
        self, client, db_session, season_with_contracts, super_admin_headers
    ):
        _, season, contracts = season_with_contracts
        headers, _user = super_admin_headers
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            r = client.get(f"/api/contract/?season_id={season.id}", headers=headers)

        assert r.status_code == 200
        data = r.json()["data"]
        assert {i["id"] for i in data["items"]} == {
            contracts["open_ended"].id,
            contracts["multi_year"].id,
        }
        assert data["pagination"] == {"total": 2, "page": 1, "size": 20, "pages": 1}


# ============================================
# Company scope
# ============================================

def _call(client, method, url, headers, **kwargs):
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


class TestContractCompanyScope:
    """Non-SUPER_ADMIN users only see and manage contracts of their own company."""

    @pytest.fixture()
    def other_contract(self, db_session, create_company, create_user):
        other = create_company(name="Other Club")
        user = create_user(email="other@test.com", username="other", company_id=other.id)
        return _staff(db_session, other, user, start_date=date(2026, 6, 1))

    def test_own_company_contract_visible(
        self, client, db_session, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="mine@test.com", username="mine", company_id=company.id)
        mine = _membership(db_session, company, user)

        response = _call(client, "get", f"/api/contract/{mine.id}", headers)
        assert response.status_code == 200

    def test_list_excludes_other_company(self, client, other_contract, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "get", "/api/contract/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert other_contract.id not in ids

    def test_get_other_company_contract_403(self, client, other_contract, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "get", f"/api/contract/{other_contract.id}", headers)
        assert response.status_code == 403

    def test_update_other_company_contract_403(self, client, other_contract, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "put", f"/api/contract/{other_contract.id}", headers,
                         json={"status": "cancelled"})
        assert response.status_code == 403

    def test_activate_other_company_contract_403(
        self, client, db_session, other_contract, auth_headers
    ):
        headers, _, _ = auth_headers
        response = _call(client, "post", f"/api/contract/{other_contract.id}/activate", headers)
        assert response.status_code == 403
        db_session.refresh(other_contract)
        assert other_contract.status == ContractStatus.DRAFT

    def test_delete_other_company_contract_403(
        self, client, db_session, other_contract, auth_headers
    ):
        headers, _, _ = auth_headers
        response = _call(client, "delete", f"/api/contract/{other_contract.id}", headers)
        assert response.status_code == 403
        assert db_session.get(Contract, other_contract.id) is not None

    def test_create_contract_in_other_company_403(
        self, client, create_company, create_user, auth_headers
    ):
        headers, _, _ = auth_headers
        other = create_company(name="Other Club")
        user = create_user(email="other2@test.com", username="other2", company_id=other.id)

        response = _call(client, "post", "/api/contract/", headers, json={
            "company_id": other.id,
            "user_id": user.id,
            "contract_type": "staff",
            "amount": "1000.00",
            "start_date": "2026-01-01",
        })
        assert response.status_code == 403

    def test_super_admin_sees_other_company_contract(
        self, client, other_contract, super_admin_headers
    ):
        headers, _ = super_admin_headers
        response = _call(client, "get", f"/api/contract/{other_contract.id}", headers)
        assert response.status_code == 200


# ============================================
# List summary
# ============================================

class TestContractSummary:

    @pytest.fixture()
    def book(self, db_session, create_company, create_user):
        company = create_company(name="Summary Club")
        player = create_user(company_id=company.id)
        coach = create_user(email="coach@test.com", username="coach", company_id=company.id)
        monthly = _plan(db_session, company, _selection(db_session, company.id, "Juniors"))
        term = _term_plan(db_session, company, _selection(db_session, company.id, "Masters"))

        _membership(db_session, company, player, plan=monthly)            # ACTIVE monthly 5000
        _membership(db_session, company, player, plan=term)               # ACTIVE term, excluded
        _staff(db_session, company, coach)                                # ACTIVE staff 120000
        _staff(db_session, company, coach, start_date=date(2026, 6, 1))   # DRAFT
        return company

    def test_counts_and_recurring_amounts(self, db_session, book):
        summary = ContractService(db_session).get_summary(ContractFilters(company_id=book.id))
        assert summary == {
            "count": 4,
            "by_status": {"draft": 1, "active": 3, "ended": 0, "cancelled": 0},
            "monthly_income": Decimal("5000.00"),
            "monthly_outcome": Decimal("120000.00"),
        }

    def test_honours_list_filters(self, db_session, book):
        summary = ContractService(db_session).get_summary(
            ContractFilters(company_id=book.id, status=ContractStatus.DRAFT)
        )
        assert summary["count"] == 1
        assert summary["monthly_outcome"] == Decimal("0")

    def test_list_endpoint_carries_summary(self, client, db_session, create_user, auth_headers):
        headers, _, company = auth_headers
        user = create_user(email="mine@test.com", username="mine", company_id=company.id)
        _membership(db_session, company, user)

        data = _call(client, "get", "/api/contract/?size=1", headers).json()["data"]
        assert data["summary"]["count"] == 1
        assert Decimal(str(data["summary"]["monthly_income"])) == Decimal("5000.00")
