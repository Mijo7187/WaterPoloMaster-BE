# ============================================
# CONTRACT TESTS
# ============================================

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from pydantic import ValidationError

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
    _add_months,
    compute_contract_status,
    month_bounds,
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
from app.features.membership.membership_model import Program
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
from app.features.wallet.wallet_model import Wallet, WalletOwnerType
from app.scheduler.contract_jobs import _daily_contract_status_job

# Most tests run "on" this day: a Jan-Mar 2026 contract is ACTIVE.
TODAY = date(2026, 1, 15)


@pytest.fixture(autouse=True)
def _today(freeze_club_today):
    freeze_club_today(TODAY)


def _monthly(start, count, amount):
    """installments_list: `count` consecutive one-month installments of `amount`."""
    items = []
    period_start = start
    for _ in range(count):
        next_start = _add_months(period_start, 1)
        items.append(dict(
            period_start=period_start,
            period_end=next_start - timedelta(days=1),
            due_date=period_start,
            amount=Decimal(amount),
        ))
        period_start = next_start
    return items


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


def _membership(db_session, company, user, installments_list=None, **kwargs):
    """A MEMBERSHIP contract. Defaults to a Jan-Mar 2026 quarter of 3 x 5000."""
    if installments_list is None:
        installments_list = _monthly(date(2026, 1, 1), 3, "5000.00")
    return ContractService(db_session).create(ContractCreate(
        company_id=company.id,
        user_id=user.id,
        contract_type=ContractType.MEMBERSHIP,
        installments_list=installments_list,
        **kwargs,
    ))


def _staff(db_session, company, user, **kwargs):
    payload = dict(
        company_id=company.id,
        user_id=user.id,
        contract_type=ContractType.STAFF,
        amount=Decimal("120000.00"),
        start_date=date(2026, 1, 1),
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
# compute_contract_status — pure
# ============================================

class TestComputeContractStatus:
    D = date(2026, 5, 10)

    def test_future_start_is_draft(self):
        assert compute_contract_status(self.D + timedelta(days=1), None, self.D) == ContractStatus.DRAFT

    def test_started_without_end_date_is_active(self):
        assert compute_contract_status(self.D - timedelta(days=30), None, self.D) == ContractStatus.ACTIVE

    def test_started_and_not_yet_ended_is_active(self):
        assert compute_contract_status(
            self.D - timedelta(days=30), self.D + timedelta(days=30), self.D
        ) == ContractStatus.ACTIVE

    def test_both_dates_before_today_is_ended(self):
        assert compute_contract_status(
            self.D - timedelta(days=30), self.D - timedelta(days=1), self.D
        ) == ContractStatus.ENDED

    def test_start_equal_today_is_active(self):
        assert compute_contract_status(self.D, None, self.D) == ContractStatus.ACTIVE

    def test_end_equal_today_is_still_active(self):
        assert compute_contract_status(
            self.D - timedelta(days=30), self.D, self.D
        ) == ContractStatus.ACTIVE

    def test_start_and_end_today_is_active(self):
        assert compute_contract_status(self.D, self.D, self.D) == ContractStatus.ACTIVE

    @pytest.mark.parametrize("start,end", [
        (D + timedelta(days=1), None),               # would be DRAFT
        (D - timedelta(days=1), None),               # would be ACTIVE
        (D - timedelta(days=9), D - timedelta(days=1)),  # would be ENDED
    ])
    def test_cancelled_is_sticky(self, start, end):
        assert compute_contract_status(
            start, end, self.D, ContractStatus.CANCELLED
        ) == ContractStatus.CANCELLED

    def test_other_current_statuses_are_recomputed(self):
        assert compute_contract_status(
            self.D - timedelta(days=9), self.D - timedelta(days=1), self.D,
            ContractStatus.ACTIVE,
        ) == ContractStatus.ENDED


class TestMonthBounds:

    def test_is_the_calendar_month(self):
        assert month_bounds(date(2026, 2, 17)) == (date(2026, 2, 1), date(2026, 2, 28))

    def test_leap_february(self):
        assert month_bounds(date(2028, 2, 1)) == (date(2028, 2, 1), date(2028, 2, 29))


# ============================================
# MEMBERSHIP create
# ============================================

class TestMembershipCreate:

    def test_writes_rows_and_derives_amount_dates_and_status(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)

        contract = _membership(db_session, company, user)

        rows = _installments(db_session, contract)
        assert [(i.period_start, i.period_end, i.due_date, i.amount) for i in rows] == [
            (date(2026, 1, 1), date(2026, 1, 31), date(2026, 1, 1), Decimal("5000.00")),
            (date(2026, 2, 1), date(2026, 2, 28), date(2026, 2, 1), Decimal("5000.00")),
            (date(2026, 3, 1), date(2026, 3, 31), date(2026, 3, 1), Decimal("5000.00")),
        ]
        assert contract.amount == Decimal("15000.00")
        assert contract.start_date == date(2026, 1, 1)
        assert contract.end_date == date(2026, 3, 31)
        assert contract.status == ContractStatus.ACTIVE

    def test_matching_explicit_values_are_accepted(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)

        contract = _membership(
            db_session, company, user,
            amount=Decimal("15000.00"),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
        assert contract.amount == Decimal("15000.00")

    def test_future_start_is_draft(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)

        contract = _membership(
            db_session, company, user,
            installments_list=_monthly(date(2026, 2, 1), 1, "5000.00"),
        )
        assert contract.status == ContractStatus.DRAFT

    def test_every_installment_field_is_taken_from_the_row(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)

        contract = _membership(db_session, company, user, installments_list=[dict(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            due_date=date(2026, 1, 10),
            amount=Decimal("15000.00"),
            waived=True,
        )])

        [row] = _installments(db_session, contract)
        assert row.due_date == date(2026, 1, 10)
        assert row.waived is True

    def test_amount_mismatch_is_422(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, amount=Decimal("14999.99"))
        assert _locs(exc) == [["amount"]]
        assert exc.value.status_code == 422

    def test_start_date_mismatch_is_422(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, start_date=date(2026, 1, 2))
        assert _locs(exc) == [["start_date"]]

    def test_end_date_mismatch_is_422(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, end_date=date(2026, 6, 30))
        assert _locs(exc) == [["end_date"]]

    def test_overlapping_rows_are_422(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)
        rows = _monthly(date(2026, 1, 1), 2, "5000.00")
        rows[1]["period_start"] = date(2026, 1, 31)  # overlaps row 0's last day

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, installments_list=rows)
        assert _locs(exc) == [["installments_list", 1, "period_start"]]

    def test_unsorted_rows_are_422(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)
        rows = list(reversed(_monthly(date(2026, 1, 1), 2, "5000.00")))

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, installments_list=rows)
        assert _locs(exc) == [["installments_list", 1, "period_start"]]

    def test_period_end_before_period_start_is_422(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        rows = _monthly(date(2026, 1, 1), 2, "5000.00")
        rows[1]["period_end"] = date(2026, 1, 20)

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, installments_list=rows)
        assert ["installments_list", 1, "period_end"] in _locs(exc)

    def test_empty_list_is_422(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, installments_list=[])
        assert _locs(exc) == [["installments_list"]]

    def test_omitted_list_without_a_plan_is_422(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)

        with pytest.raises(ValidationException):
            ContractService(db_session).create(ContractCreate(
                company_id=company.id,
                user_id=user.id,
                contract_type=ContractType.MEMBERSHIP,
                amount=Decimal("5000.00"),
                start_date=date(2026, 1, 1),
            ))

    def test_due_date_is_required(self):
        row = _monthly(date(2026, 1, 1), 1, "5000.00")[0]
        del row["due_date"]
        with pytest.raises(ValidationError):
            ContractCreate(
                company_id=1, user_id=1, contract_type=ContractType.MEMBERSHIP,
                installments_list=[row],
            )

    def test_negative_row_amount_is_rejected(self):
        with pytest.raises(ValidationError):
            ContractCreate(
                company_id=1, user_id=1, contract_type=ContractType.MEMBERSHIP,
                installments_list=_monthly(date(2026, 1, 1), 1, "-1.00"),
            )

    def test_scholarship_is_one_zero_row_and_is_never_billed(
        self, db_session, parties
    ):
        from app.scheduler.billing_jobs import _nightly_billing_job

        company, user = parties()
        contract = _membership(
            db_session, company, user,
            installments_list=_monthly(date(2026, 1, 1), 1, "0.00"),
        )
        assert contract.amount == Decimal("0.00")
        assert contract.status == ContractStatus.ACTIVE

        assert _nightly_billing_job(db_session, on_date=date(2026, 1, 31)) == 0
        assert _payments(db_session) == []

    def test_client_status_is_ignored(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)

        contract = _membership(db_session, company, user, status=ContractStatus.ENDED)
        assert contract.status == ContractStatus.ACTIVE

    def test_cancelled_on_create_is_422(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)

        with pytest.raises(ValidationException) as exc:
            _membership(db_session, company, user, status=ContractStatus.CANCELLED)
        assert _locs(exc) == [["status"]]

    def test_response_includes_the_installments(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _membership(db_session, company, user)

        dumped = ContractResponse.model_validate(contract).model_dump()
        assert len(dumped["installments"]) == 3


class TestValidationErrorShape:
    """422s carry field-level {loc, msg} the frontend can pin on a row."""

    def _post(self, client, headers, body):
        with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
            mock_get.return_value = headers["Authorization"].split(" ")[1]
            return client.post("/api/contract/", headers=headers, json=body)

    def _body(self, company, user, rows):
        return {
            "company_id": company.id,
            "user_id": user.id,
            "contract_type": "membership",
            "installments_list": [
                {k: (str(v) if not isinstance(v, bool) else v) for k, v in r.items()}
                for r in rows
            ],
        }

    def test_service_error_points_at_the_row(
        self, client, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)
        rows = _monthly(date(2026, 1, 1), 2, "5000.00")
        rows[1]["period_end"] = date(2026, 1, 20)

        r = self._post(client, headers, self._body(company, user, rows))

        assert r.status_code == 422, r.text
        assert {"loc": ["installments_list", 1, "period_end"],
                "msg": "period_end must be on or after period_start."} in r.json()["errors"]

    def test_schema_error_uses_the_same_shape(
        self, client, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)
        rows = _monthly(date(2026, 1, 1), 1, "5000.00")
        del rows[0]["due_date"]

        r = self._post(client, headers, self._body(company, user, rows))

        assert r.status_code == 422
        assert ["installments_list", 0, "due_date"] in [
            e["loc"] for e in r.json()["errors"]
        ]

    def test_valid_request_creates_the_contract(
        self, client, db_session, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)

        r = self._post(client, headers, self._body(
            company, user, _monthly(date(2026, 1, 1), 3, "5000.00")
        ))

        assert r.status_code in (200, 201), r.text
        [contract_id] = r.json()["data"]
        contract = db_session.get(Contract, contract_id)
        assert contract.amount == Decimal("15000.00")
        assert contract.status == ContractStatus.ACTIVE


# ============================================
# MEMBERSHIP from a catalog plan
# ============================================

def _plan(db_session, company, **kwargs):
    payload = dict(
        company_id=company.id,
        name="Senior Waterpolo",
        program=Program.WATERPOLO,
        months_count=3,
        price_month=Decimal("5000.00"),
        installments_count=3,
    )
    payload.update(kwargs)
    return MembershipService(db_session).create(MembershipCreate(**payload))


def _from_plan(db_session, company, user, plan, **kwargs):
    payload = dict(
        company_id=company.id,
        user_id=user.id,
        contract_type=ContractType.MEMBERSHIP,
        membership_id=plan.id,
        start_date=date(2026, 1, 1),
    )
    payload.update(kwargs)
    return ContractService(db_session).create(ContractCreate(**payload))


class TestContractFromMembership:
    """membership_id prefills installments_list when it is omitted, then goes inert."""

    def test_terms_are_taken_from_the_plan(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        plan = _plan(db_session, company)

        contract = _from_plan(db_session, company, user, plan)

        assert contract.membership_id == plan.id
        assert contract.amount == Decimal("15000.00")
        assert contract.end_date == date(2026, 3, 31)
        assert [(i.period_start, i.amount) for i in _installments(db_session, contract)] == [
            (date(2026, 1, 1), Decimal("5000.00")),
            (date(2026, 2, 1), Decimal("5000.00")),
            (date(2026, 3, 1), Decimal("5000.00")),
        ]

    def test_an_explicit_amount_is_split_over_the_plan(
        self, db_session, create_user, create_company
    ):
        """100 / 3 does not divide cleanly — the remainder lands on the last row."""
        company = create_company()
        user = create_user(company_id=company.id)
        plan = _plan(db_session, company)

        contract = _from_plan(db_session, company, user, plan, amount=Decimal("100.00"))

        amounts = [i.amount for i in _installments(db_session, contract)]
        assert amounts == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]

    def test_an_explicit_list_beats_the_plan(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        plan = _plan(db_session, company)

        contract = _from_plan(
            db_session, company, user, plan,
            installments_list=_monthly(date(2026, 1, 1), 1, "12000.00"),
        )

        assert contract.amount == Decimal("12000.00")
        assert len(_installments(db_session, contract)) == 1

    def test_contract_does_not_follow_the_plan_after_signing(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        plan = _plan(db_session, company)
        contract = _from_plan(db_session, company, user, plan)

        MembershipService(db_session).update(
            plan.id, MembershipUpdate(price_month=Decimal("9000.00"))
        )
        db_session.refresh(contract)

        assert contract.amount == Decimal("15000.00")

    def test_a_plan_from_another_company_is_422(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        other = create_company(name="Other Club")
        user = create_user(company_id=company.id)
        plan = _plan(db_session, other)

        with pytest.raises(ValidationException) as exc:
            _from_plan(db_session, company, user, plan)
        assert _locs(exc) == [["membership_id"]]

    def test_an_unknown_plan_is_404(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)

        with pytest.raises(NotFoundException):
            ContractService(db_session).create(ContractCreate(
                company_id=company.id,
                user_id=user.id,
                contract_type=ContractType.MEMBERSHIP,
                membership_id=9999,
                start_date=date(2026, 1, 1),
            ))


# ============================================
# STAFF create
# ============================================

class TestStaffCreate:

    def test_status_is_computed_and_the_current_month_is_added(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)

        contract = _staff(db_session, company, user)

        assert contract.status == ContractStatus.ACTIVE
        [row] = _installments(db_session, contract)
        assert (row.period_start, row.period_end) == month_bounds(TODAY)
        assert row.amount == Decimal("120000.00")

    def test_future_start_is_draft_with_no_installments(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)

        contract = _staff(db_session, company, user, start_date=date(2026, 3, 1))

        assert contract.status == ContractStatus.DRAFT
        assert _installments(db_session, contract) == []

    def test_installments_list_is_422(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)

        with pytest.raises(ValidationException) as exc:
            _staff(
                db_session, company, user,
                installments_list=_monthly(date(2026, 1, 1), 1, "120000.00"),
            )
        assert _locs(exc) == [["installments_list"]]

    def test_membership_id_is_422(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)
        plan = _plan(db_session, company)

        with pytest.raises(ValidationException) as exc:
            _staff(db_session, company, user, membership_id=plan.id)
        assert _locs(exc) == [["membership_id"]]

    @pytest.mark.parametrize("amount", [None, Decimal("0")])
    def test_amount_is_required_and_positive(
        self, db_session, create_user, create_company, amount
    ):
        company = create_company()
        user = create_user(company_id=company.id)

        with pytest.raises(ValidationException) as exc:
            _staff(db_session, company, user, amount=amount)
        assert _locs(exc) == [["amount"]]

    def test_end_before_start_is_422(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)

        with pytest.raises(ValidationException) as exc:
            _staff(db_session, company, user, end_date=date(2025, 12, 31))
        assert _locs(exc) == [["end_date"]]


# ============================================
# Update
# ============================================

class TestContractUpdate:

    def test_client_active_or_ended_is_overwritten(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
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
        self, db_session, create_user, create_company, freeze_club_today
    ):
        company = create_company()
        user = create_user(company_id=company.id)
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

    def test_staff_end_date_change_recomputes_status(
        self, db_session, parties
    ):
        company, user = parties()
        contract = _staff(db_session, company, user)

        updated = ContractService(db_session).update(
            contract.id, ContractUpdate(end_date=date(2026, 1, 10))
        )
        assert updated.status == ContractStatus.ENDED

    def test_staff_amount_and_end_date_are_updatable(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _staff(db_session, company, user)

        updated = ContractService(db_session).update(contract.id, ContractUpdate(
            amount=Decimal("130000.00"), end_date=date(2026, 12, 31)
        ))
        assert updated.amount == Decimal("130000.00")
        assert updated.end_date == date(2026, 12, 31)
        assert updated.status == ContractStatus.ACTIVE

    def test_staff_end_before_start_is_422(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _staff(db_session, company, user)

        with pytest.raises(ValidationException) as exc:
            ContractService(db_session).update(
                contract.id, ContractUpdate(end_date=date(2025, 12, 1))
            )
        assert _locs(exc) == [["end_date"]]

    def test_membership_amount_drift_is_422(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _membership(db_session, company, user)

        with pytest.raises(ValidationException) as exc:
            ContractService(db_session).update(
                contract.id, ContractUpdate(amount=Decimal("12000.00"))
            )
        assert _locs(exc) == [["amount"]]

    def test_membership_end_date_drift_is_422(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _membership(db_session, company, user)

        with pytest.raises(ValidationException) as exc:
            ContractService(db_session).update(
                contract.id, ContractUpdate(end_date=date(2026, 6, 30))
            )
        assert _locs(exc) == [["end_date"]]

    def test_membership_matching_values_are_accepted(
        self, db_session, create_user, create_company
    ):
        """The frontend may echo the (disabled) fields back unchanged."""
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _membership(db_session, company, user)

        updated = ContractService(db_session).update(contract.id, ContractUpdate(
            amount=Decimal("15000.00"), end_date=date(2026, 3, 31)
        ))
        assert updated.amount == Decimal("15000.00")


class TestInstallmentEditResync:
    """Editing a single installment re-syncs the MEMBERSHIP contract."""

    def test_amount_edit_resyncs_contract_amount(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _membership(db_session, company, user)
        first = _installments(db_session, contract)[0]

        ContractInstallmentService(db_session).update(
            first.id, ContractInstallmentUpdate(amount=Decimal("4000.00"))
        )

        db_session.refresh(contract)
        assert contract.amount == Decimal("14000.00")

    def test_last_period_end_edit_resyncs_end_date_and_status(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _membership(db_session, company, user)
        last = _installments(db_session, contract)[-1]

        ContractInstallmentService(db_session).update(
            last.id, ContractInstallmentUpdate(period_end=date(2026, 4, 30))
        )

        db_session.refresh(contract)
        assert contract.end_date == date(2026, 4, 30)
        assert contract.status == ContractStatus.ACTIVE

    def test_deleting_the_last_row_resyncs(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _membership(db_session, company, user)
        last = _installments(db_session, contract)[-1]

        ContractInstallmentService(db_session).delete(last.id)

        db_session.refresh(contract)
        assert contract.amount == Decimal("10000.00")
        assert contract.end_date == date(2026, 2, 28)

    def test_staff_contract_is_not_resynced(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
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

    def test_does_not_generate_membership_installments(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _membership(db_session, company, user)

        ContractService(db_session).activate(contract.id)
        ContractService(db_session).activate(contract.id)

        assert len(_installments(db_session, contract)) == 3

    def test_moves_a_stale_draft_to_active(
        self, db_session, create_user, create_company, freeze_club_today
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _staff(db_session, company, user, start_date=date(2026, 2, 1))
        assert contract.status == ContractStatus.DRAFT

        freeze_club_today(date(2026, 2, 3))
        refreshed = ContractService(db_session).activate(contract.id)

        assert refreshed.status == ContractStatus.ACTIVE
        [row] = _installments(db_session, contract)
        assert row.period_start == date(2026, 2, 1)


# ============================================
# Daily status job
# ============================================

class TestDailyContractStatusJob:

    def test_moves_draft_to_active(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _staff(db_session, company, user, start_date=date(2026, 2, 1))

        assert _daily_contract_status_job(db_session, on_date=date(2026, 1, 31)) == 0
        assert _daily_contract_status_job(db_session, on_date=date(2026, 2, 1)) == 1

        db_session.refresh(contract)
        assert contract.status == ContractStatus.ACTIVE
        # A STAFF contract becoming ACTIVE gets that month's installment.
        assert [i.period_start for i in _installments(db_session, contract)] == [
            date(2026, 2, 1)
        ]

    def test_moves_active_to_ended_and_bills_leftovers(self, db_session, parties):
        company, user = parties()
        contract = _membership(db_session, company, user)

        # end_date 2026-03-31 is still "today or later" on the 31st.
        assert _daily_contract_status_job(db_session, on_date=date(2026, 3, 31)) == 0
        assert _daily_contract_status_job(db_session, on_date=date(2026, 4, 1)) == 1

        db_session.refresh(contract)
        assert contract.status == ContractStatus.ENDED
        payments = _payments(db_session)
        assert len(payments) == 3
        assert all(p.status == PaymentStatus.PENDING for p in payments)
        assert all(p.payment_type == PaymentTypeCode.USER_MEMBERSHIP_FEE for p in payments)
        assert all(p.sender_wallet_id == user.w_id for p in payments)
        assert all(p.receiver_wallet_id == company.w_id for p in payments)

    def test_leaves_cancelled_alone(self, db_session, create_user, create_company):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _staff(db_session, company, user, start_date=date(2026, 2, 1))
        ContractService(db_session).update(
            contract.id, ContractUpdate(status=ContractStatus.CANCELLED)
        )

        assert _daily_contract_status_job(db_session, on_date=date(2026, 5, 1)) == 0

        db_session.refresh(contract)
        assert contract.status == ContractStatus.CANCELLED

    def test_is_idempotent(self, db_session, parties):
        company, user = parties()
        _membership(db_session, company, user)
        _daily_contract_status_job(db_session, on_date=date(2026, 4, 1))

        assert _daily_contract_status_job(db_session, on_date=date(2026, 4, 1)) == 0
        assert len(_payments(db_session)) == 3

    def test_missing_wallet_keeps_it_active_for_a_retry(self, db_session, parties):
        company, user = parties(user_wallet=False)
        contract = _membership(db_session, company, user)

        assert _daily_contract_status_job(db_session, on_date=date(2026, 4, 1)) == 0

        db_session.refresh(contract)
        assert contract.status == ContractStatus.ACTIVE
        assert _payments(db_session) == []


# ============================================
# Ending — settle whatever is left
# ============================================

class TestContractEndedBilling:

    def test_only_unbilled_installments_are_billed(self, db_session, parties):
        from app.scheduler.billing_jobs import _nightly_billing_job

        company, user = parties()
        _membership(db_session, company, user)
        assert _nightly_billing_job(db_session, on_date=date(2026, 1, 15)) == 1

        _daily_contract_status_job(db_session, on_date=date(2026, 4, 1))

        payments = _payments(db_session)
        assert len(payments) == 3
        assert len({p.payable_id for p in payments}) == 3

    def test_waived_installment_is_not_billed(self, db_session, parties):
        company, user = parties()
        contract = _membership(db_session, company, user)
        waived = _installments(db_session, contract)[1]
        ContractInstallmentService(db_session).waive(waived.id)

        _daily_contract_status_job(db_session, on_date=date(2026, 4, 1))

        payments = _payments(db_session)
        assert len(payments) == 2
        assert waived.id not in {p.payable_id for p in payments}

    def test_backdated_contract_is_ended_and_billed_at_create(
        self, db_session, parties, freeze_club_today
    ):
        company, user = parties()
        freeze_club_today(date(2026, 4, 1))

        contract = _membership(db_session, company, user)

        assert contract.status == ContractStatus.ENDED
        assert len(_payments(db_session)) == 3

    def test_backdated_contract_without_wallet_is_refused(
        self, db_session, parties, freeze_club_today
    ):
        company, user = parties(user_wallet=False)
        freeze_club_today(date(2026, 4, 1))

        with pytest.raises(BadRequestException, match="no wallet"):
            _membership(db_session, company, user)

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
        contract = _membership(db_session, company, user)
        _daily_contract_status_job(db_session, on_date=date(2026, 4, 1))

        ContractService(db_session).update(
            contract.id, ContractUpdate(amount=Decimal("15000.00"))
        )

        assert len(_payments(db_session)) == 3


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

    def test_membership_and_staff_are_both_included(
        self, db_session, season_with_contracts, create_user
    ):
        """A season's "Korisnici" is anyone under contract that season."""
        company, season, contracts = season_with_contracts
        user = create_user(
            company_id=company.id, email="member@test.com", username="member"
        )
        membership = Contract(
            company_id=company.id,
            user_id=user.id,
            contract_type=ContractType.MEMBERSHIP,
            amount=Decimal("5000.00"),
            start_date=date(2025, 10, 1),
            end_date=date(2026, 5, 31),
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
