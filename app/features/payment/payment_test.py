import uuid
from datetime import date, datetime
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


def test_second_wallet_id_keeps_only_payments_between_the_two(db_session, wallets):
    a, b = wallets
    other = Wallet(owner_id=2, owner_type=WalletOwnerType.COMPANY)
    db_session.add(other)
    db_session.commit()

    db_session.add_all([
        _payment(a.id, b.id, 1),      # a → b
        _payment(b.id, a.id, 2),      # b → a
        _payment(a.id, other.id, 3),  # a with someone else
        _payment(other.id, b.id, 4),  # b with someone else
    ])
    db_session.commit()

    items, total = PaymentService(db_session).get_list(
        filters=PaymentFilters(wallet_id=a.id, second_wallet_id=b.id)
    )
    assert total == 2
    assert sorted(i.created_at.day for i in items) == [1, 2]

    # Summary is seen from wallet_id's side: a paid 10 out and got 10 in (both PENDING).
    summary = PaymentService(db_session).get_summary(
        PaymentFilters(wallet_id=a.id, second_wallet_id=b.id)
    )
    assert summary["count"] == 2
    assert summary["pending_income"] == Decimal("10.00")
    assert summary["pending_outcome"] == Decimal("10.00")


def test_date_range_filter_includes_both_end_days(db_session, wallets):
    a, b = wallets
    db_session.add_all([_payment(a.id, b.id, day) for day in (1, 2, 5, 6)])
    db_session.commit()

    # Payments are at 10:00 — date_to=5 must still keep the one on the 5th.
    items, total = PaymentService(db_session).get_list(
        filters=PaymentFilters(date_from=date(2026, 7, 2), date_to=date(2026, 7, 5))
    )
    assert total == 2
    assert sorted(i.created_at.day for i in items) == [2, 5]

    # The summary covers the same period.
    summary = PaymentService(db_session).get_summary(
        PaymentFilters(wallet_id=a.id, date_from=date(2026, 7, 2), date_to=date(2026, 7, 5))
    )
    assert summary["count"] == 2


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
# RESOLVED PAYABLE SHAPE
# ============================================
# A membership/salary due points at a contract_installment, which on its own
# only carries a contract_id. The nested contract is what names who owes it, so
# it is serialized with the payable — see PayableContractInstallmentResponse.

def test_installment_payable_carries_its_contract(
    db_session, wallets, create_company, create_user
):
    from datetime import date

    from app.features.contract.contract_model import (
        Contract,
        ContractStatus,
        ContractType,
    )
    from app.features.contract_installment.contract_installment_model import (
        ContractInstallment,
    )
    from app.features.payment.payment_schemas import PaymentResponse

    sender, receiver = wallets
    club = create_company(name="Club")
    player = create_user(email="player@test.com", username="player", company_id=club.id)

    contract = Contract(
        company_id=club.id,
        user_id=player.id,
        contract_type=ContractType.MEMBERSHIP,
        amount=Decimal("50.00"),
        start_date=date(2026, 1, 1),
        status=ContractStatus.ACTIVE,
    )
    db_session.add(contract)
    db_session.commit()

    installment = ContractInstallment(
        contract_id=contract.id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        due_date=date(2026, 1, 10),
        amount=Decimal("50.00"),
    )
    db_session.add(installment)
    db_session.commit()

    payment = Payment(
        id=uuid.uuid4(),
        sender_wallet_id=sender.id,
        receiver_wallet_id=receiver.id,
        payment_type=PaymentTypeCode.USER_MEMBERSHIP_FEE,
        amount=Decimal("50.00"),
        status=PaymentStatus.PENDING,
        payable_type=PayableType.CONTRACT_INSTALLMENT,
        payable_id=installment.id,
    )
    db_session.add(payment)
    db_session.commit()

    obj = PaymentService(db_session).get_by_id(payment.id)
    payable = PaymentResponse.model_validate(obj).model_dump()["payable"]

    assert payable["id"] == installment.id
    assert payable["contract"]["id"] == contract.id
    assert payable["contract"]["amount"] == Decimal("50.00")
    # The contract's own nested user comes along — who owes the due.
    assert payable["contract"]["user"]["email"] == "player@test.com"


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

    def test_summary_is_company_scoped(self, client, scoped):
        """An ADMIN looking at another company's wallet only gets totals over
        the payments that touch their own company."""
        headers, _, w, _ = scoped
        response = _call(client, "get", f"/api/payment/?wallet_id={w['other_company'].id}", headers)
        summary = response.json()["data"]["summary"]
        # Only "cross" (other_company → my_company, PENDING 10) is visible;
        # "theirs" (other_user → other_company) is outside the admin's scope.
        assert summary["count"] == 1
        assert Decimal(str(summary["pending_outcome"])) == Decimal("10.00")
        assert Decimal(str(summary["pending_income"])) == Decimal("0")

    def test_admin_summary_is_seen_from_own_club_wallet(self, client, db_session, scoped):
        headers, _, w, _ = scoped
        db_session.add(_paid(w["my_user"].id, w["my_company"].id, "50.00", PaymentStatus.COMPLETED))
        db_session.commit()

        summary = _call(client, "get", "/api/payment/", headers).json()["data"]["summary"]
        # In scope: "mine" + "cross" (both PENDING 10 into my club) + the 50 above.
        assert summary["count"] == 3
        assert Decimal(str(summary["total_income"])) == Decimal("50.00")
        assert Decimal(str(summary["pending_income"])) == Decimal("20.00")
        assert Decimal(str(summary["total_outcome"])) == Decimal("0")

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


# ============================================
# List summary
# ============================================

def _paid(sender_id, receiver_id, amount, status):
    return Payment(
        id=uuid.uuid4(),
        sender_wallet_id=sender_id,
        receiver_wallet_id=receiver_id,
        payment_type=PaymentTypeCode.CLUB_SALARY_USER,
        amount=Decimal(amount),
        status=status,
    )


class TestPaymentSummary:

    @pytest.fixture()
    def ledger(self, db_session, wallets):
        a, b = wallets
        db_session.add_all([
            _paid(b.id, a.id, "100.00", PaymentStatus.COMPLETED),  # a income
            _paid(b.id, a.id, "50.00", PaymentStatus.COMPLETED),   # a income
            _paid(a.id, b.id, "30.00", PaymentStatus.COMPLETED),   # a outcome
            _paid(b.id, a.id, "20.00", PaymentStatus.PENDING),     # a pending in
            _paid(a.id, b.id, "15.00", PaymentStatus.PENDING),     # a pending out
            _paid(a.id, b.id, "40.00", PaymentStatus.DEBT),        # a owes, overdue
            _paid(b.id, a.id, "25.00", PaymentStatus.DEBT),        # owed to a, overdue
            _paid(b.id, a.id, "999.00", PaymentStatus.FAILED),     # in no bucket
        ])
        db_session.commit()
        return a, b

    def test_buckets_from_the_wallets_side(self, db_session, ledger):
        a, _ = ledger
        summary = PaymentService(db_session).get_summary(PaymentFilters(wallet_id=a.id))
        assert summary == {
            "total_income": Decimal("150.00"),
            "total_outcome": Decimal("30.00"),
            "balance": Decimal("120.00"),
            "pending_income": Decimal("20.00"),
            "pending_outcome": Decimal("15.00"),
            "total_debt": Decimal("40.00"),
            "debt_receivable": Decimal("25.00"),
            "count": 8,
        }

    def test_other_side_mirrors(self, db_session, ledger):
        _, b = ledger
        summary = PaymentService(db_session).get_summary(PaymentFilters(wallet_id=b.id))
        assert summary["total_income"] == Decimal("30.00")
        assert summary["total_outcome"] == Decimal("150.00")
        assert summary["total_debt"] == Decimal("25.00")
        assert summary["debt_receivable"] == Decimal("40.00")

    def test_ignores_pagination(self, db_session, ledger):
        a, _ = ledger
        summary = PaymentService(db_session).get_summary(
            PaymentFilters(wallet_id=a.id, size=1, page=3)
        )
        assert summary["total_income"] == Decimal("150.00")
        assert summary["count"] == 8

    def test_honours_list_filters(self, db_session, ledger):
        a, _ = ledger
        summary = PaymentService(db_session).get_summary(
            PaymentFilters(wallet_id=a.id, status=PaymentStatus.DEBT)
        )
        assert summary["total_income"] == Decimal("0")
        assert summary["total_debt"] == Decimal("40.00")
        assert summary["count"] == 2

    def test_whole_app_is_seen_from_the_clubs_side(self, db_session, wallets):
        user_w, club_w = wallets
        pool_w = Wallet(owner_id=2, owner_type=WalletOwnerType.COMPANY)
        db_session.add(pool_w)
        db_session.commit()

        def pay(sender, receiver, code, amount, status):
            p = _paid(sender.id, receiver.id, amount, status)
            p.payment_type = code
            return p

        db_session.add_all([
            pay(user_w, club_w, PaymentTypeCode.USER_MEMBERSHIP_FEE, "100.00", PaymentStatus.COMPLETED),
            pay(user_w, club_w, PaymentTypeCode.USER_TOURNAMENT_FEE, "20.00", PaymentStatus.PENDING),
            pay(user_w, club_w, PaymentTypeCode.USER_MEMBERSHIP_FEE, "40.00", PaymentStatus.DEBT),
            pay(club_w, user_w, PaymentTypeCode.CLUB_SALARY_USER, "60.00", PaymentStatus.COMPLETED),
            pay(club_w, pool_w, PaymentTypeCode.CLUB_TRAINING_POOL, "30.00", PaymentStatus.COMPLETED),
        ])
        db_session.commit()

        summary = PaymentService(db_session).get_summary(PaymentFilters())
        assert summary["total_income"] == Decimal("100.00")
        assert summary["total_outcome"] == Decimal("90.00")
        assert summary["balance"] == Decimal("10.00")
        assert summary["pending_income"] == Decimal("20.00")
        assert summary["debt_receivable"] == Decimal("40.00")
        assert summary["total_debt"] == Decimal("0")
        assert summary["count"] == 5


class TestPaymentEndpoints:

    def test_list_always_returns_summary(self, client, db_session, super_admin_headers, wallets):
        a, b = wallets
        db_session.add(_paid(b.id, a.id, "10.00", PaymentStatus.COMPLETED))
        db_session.commit()
        headers, _ = super_admin_headers

        data = _call(client, "get", "/api/payment/", headers).json()["data"]
        assert data["summary"]["count"] == 1
        assert data["pagination"]["total"] == 1

        data = _call(client, "get", f"/api/payment/?wallet_id={a.id}", headers).json()["data"]
        assert Decimal(str(data["summary"]["total_income"])) == Decimal("10.00")

    def test_bad_uuid_is_422(self, client, auth_headers):
        headers, _, _ = auth_headers
        assert _call(client, "get", "/api/payment/not-a-uuid", headers).status_code == 422

    def test_create_returns_full_payment(self, client, db_session, super_admin_headers, create_company, create_training):
        headers, _ = super_admin_headers
        company = create_company(name="Club")
        pool = create_company(name="Pool")
        mine = Wallet(owner_id=company.id, owner_type=WalletOwnerType.COMPANY)
        theirs = Wallet(owner_id=pool.id, owner_type=WalletOwnerType.COMPANY)
        db_session.add_all([mine, theirs])
        db_session.commit()
        training = create_training(company_id=company.id, pool_id=pool.id)

        response = _call(client, "post", "/api/payment/", headers, json={
            "sender_wallet_id": str(mine.id),
            "receiver_wallet_id": str(theirs.id),
            "payment_type": "club_training_pool",
            "amount": "100.00",
            "payable_type": "training",
            "payable_id": training.id,
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["sender_wallet_id"] == str(mine.id)
        assert data["status"] == "pending"

