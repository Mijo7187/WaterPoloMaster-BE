# ============================================
# CONTRACT INSTALLMENT TESTS - per-row editing
# ============================================

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.core.api.exceptions import ValidationException
from app.features.contract.contract_model import ContractType
from app.features.contract.contract_schemas import ContractCreate
from app.features.contract.contract_service import ContractService, _add_months
from app.features.contract_installment.contract_installment_model import (
    ContractInstallment,
)
from app.features.contract_installment.contract_installment_schemas import (
    ContractInstallmentCreate,
    ContractInstallmentUpdate,
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


@pytest.fixture(autouse=True)
def _today(freeze_club_today):
    freeze_club_today(date(2026, 1, 15))


def _monthly(start, count, amount):
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


def _quarter(db_session, company, user):
    """A Jan-Mar 2026 MEMBERSHIP of 3 x 5000."""
    return ContractService(db_session).create(ContractCreate(
        company_id=company.id,
        user_id=user.id,
        contract_type=ContractType.MEMBERSHIP,
        installments_list=_monthly(date(2026, 1, 1), 3, "5000.00"),
    ))


def _rows(db_session, contract):
    return (
        db_session.query(ContractInstallment)
        .filter(ContractInstallment.contract_id == contract.id)
        .order_by(ContractInstallment.period_start)
        .all()
    )


def _call(client, method, url, headers, **kwargs):
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


def _wallet(db_session, owner_id, owner_type):
    wallet = Wallet(owner_id=owner_id, owner_type=owner_type, name="w")
    db_session.add(wallet)
    db_session.commit()
    return wallet


class TestContractDetailRows:
    """GET /contract/{id} is enough for the edit screen — rows carry payment state."""

    def test_rows_carry_payment_state(
        self, client, db_session, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)
        contract = _quarter(db_session, company, user)
        first = _rows(db_session, contract)[0]
        db_session.add(Payment(
            sender_wallet_id=_wallet(db_session, user.id, WalletOwnerType.USER).id,
            receiver_wallet_id=_wallet(db_session, company.id, WalletOwnerType.COMPANY).id,
            payment_type=PaymentTypeCode.USER_MEMBERSHIP_FEE,
            amount=Decimal("2000.00"),
            status=PaymentStatus.COMPLETED,
            payable_type=PayableType.CONTRACT_INSTALLMENT,
            payable_id=first.id,
        ))
        db_session.commit()

        r = _call(client, "get", f"/api/contract/{contract.id}", headers)

        assert r.status_code == 200, r.text
        rows = r.json()["data"]["installments"]
        assert [row["period_start"] for row in rows] == [
            "2026-01-01", "2026-02-01", "2026-03-01",
        ]
        assert rows[0]["payment_status"] == "partial"
        assert Decimal(str(rows[0]["paid_amount"])) == Decimal("2000.00")
        assert rows[1]["payment_status"] == "pending"

    def test_update_response_rows_carry_payment_state_too(
        self, db_session, create_user, create_company
    ):
        from app.features.contract.contract_schemas import (
            ContractResponse,
            ContractUpdate,
        )

        company = create_company()
        user = create_user(company_id=company.id)
        contract = _quarter(db_session, company, user)

        updated = ContractService(db_session).update(
            contract.id, ContractUpdate(signed_at=None)
        )

        rows = ContractResponse.model_validate(updated).model_dump()["installments"]
        assert all(row["payment_status"] == "pending" for row in rows)


class TestEditOneRow:

    def test_row_edit_resyncs_the_contract(
        self, client, db_session, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)
        contract = _quarter(db_session, company, user)
        last = _rows(db_session, contract)[-1]

        r = _call(client, "put", f"/api/contract-installment/{last.id}", headers, json={
            "amount": "7000.00", "period_end": "2026-04-30",
        })

        assert r.status_code == 200, r.text
        db_session.refresh(contract)
        assert contract.amount == Decimal("17000.00")
        assert contract.end_date == date(2026, 4, 30)

    def test_amount_zero_is_accepted_and_counts_as_paid(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _quarter(db_session, company, user)
        first = _rows(db_session, contract)[0]
        service = ContractInstallmentService(db_session)

        service.update(first.id, ContractInstallmentUpdate(amount=Decimal("0")))

        db_session.refresh(contract)
        assert contract.amount == Decimal("10000.00")
        assert service.get_by_id(first.id).payment_status == "paid"

    def test_overlapping_the_next_row_is_422(
        self, client, db_session, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)
        contract = _quarter(db_session, company, user)
        first = _rows(db_session, contract)[0]

        r = _call(client, "put", f"/api/contract-installment/{first.id}", headers, json={
            "period_end": "2026-02-10",
        })

        assert r.status_code == 422
        assert r.json()["errors"][0]["loc"] == ["period_start"]
        db_session.refresh(contract)
        assert contract.amount == Decimal("15000.00")

    def test_period_end_before_period_start_is_422(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _quarter(db_session, company, user)
        first = _rows(db_session, contract)[0]

        with pytest.raises(ValidationException) as exc:
            ContractInstallmentService(db_session).update(
                first.id, ContractInstallmentUpdate(period_end=date(2025, 12, 31))
            )
        assert exc.value.field_errors[0]["loc"] == ["period_end"]

    def test_adding_a_row_that_overlaps_is_422(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _quarter(db_session, company, user)

        with pytest.raises(ValidationException):
            ContractInstallmentService(db_session).create(ContractInstallmentCreate(
                contract_id=contract.id,
                period_start=date(2026, 3, 15),
                period_end=date(2026, 4, 14),
                due_date=date(2026, 3, 15),
                amount=Decimal("1000.00"),
            ))

    def test_adding_a_row_after_the_last_one_extends_the_contract(
        self, db_session, create_user, create_company
    ):
        company = create_company()
        user = create_user(company_id=company.id)
        contract = _quarter(db_session, company, user)

        ContractInstallmentService(db_session).create(ContractInstallmentCreate(
            contract_id=contract.id,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            due_date=date(2026, 4, 1),
            amount=Decimal("5000.00"),
        ))

        db_session.refresh(contract)
        assert contract.amount == Decimal("20000.00")
        assert contract.end_date == date(2026, 4, 30)


class TestCompanyScope:
    """An ADMIN only sees and edits installments of their own company's contracts."""

    @pytest.fixture()
    def other_row(self, db_session, create_company, create_user):
        other = create_company(name="Other Club")
        user = create_user(email="o@test.com", username="o", company_id=other.id)
        contract = _quarter(db_session, other, user)
        return contract, _rows(db_session, contract)[0]

    def test_get_other_company_row_is_403(self, client, other_row, auth_headers):
        headers, _, _ = auth_headers
        _, row = other_row
        r = _call(client, "get", f"/api/contract-installment/{row.id}", headers)
        assert r.status_code == 403

    def test_list_by_other_company_contract_is_empty(
        self, client, other_row, auth_headers
    ):
        headers, _, _ = auth_headers
        contract, _ = other_row
        r = _call(
            client, "get", f"/api/contract-installment/?contract_id={contract.id}", headers
        )
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []

    def test_update_other_company_row_is_403(self, client, other_row, auth_headers):
        headers, _, _ = auth_headers
        _, row = other_row
        r = _call(client, "put", f"/api/contract-installment/{row.id}", headers,
                  json={"amount": "1.00"})
        assert r.status_code == 403

    def test_delete_other_company_row_is_403(
        self, client, db_session, other_row, auth_headers
    ):
        headers, _, _ = auth_headers
        _, row = other_row
        r = _call(client, "delete", f"/api/contract-installment/{row.id}", headers)
        assert r.status_code == 403
        assert db_session.get(ContractInstallment, row.id) is not None

    def test_add_row_to_other_company_contract_is_403(
        self, client, other_row, auth_headers
    ):
        headers, _, _ = auth_headers
        contract, _ = other_row
        r = _call(client, "post", "/api/contract-installment/", headers, json={
            "contract_id": contract.id,
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
            "due_date": "2026-04-01",
            "amount": "100.00",
        })
        assert r.status_code == 403

    def test_own_company_list_works(
        self, client, db_session, create_user, auth_headers
    ):
        headers, _, company = auth_headers
        user = create_user(email="p@test.com", username="p", company_id=company.id)
        contract = _quarter(db_session, company, user)

        r = _call(
            client, "get",
            f"/api/contract-installment/?contract_id={contract.id}&order_by=period_start",
            headers,
        )
        assert r.status_code == 200
        assert len(r.json()["data"]["items"]) == 3

    def test_super_admin_sees_every_company(
        self, client, other_row, super_admin_headers
    ):
        headers, _ = super_admin_headers
        _, row = other_row
        r = _call(client, "get", f"/api/contract-installment/{row.id}", headers)
        assert r.status_code == 200
