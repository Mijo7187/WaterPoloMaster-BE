# ============================================
# BILLING JOBS - Scheduled fee generation
# ============================================
# Two jobs:
#   * Monthly (1st of the month): every ACTIVE recurring contract covering the
#     month gets that month's installment (1st - last day, amount =
#     contract.amount) and its PENDING payment. Recurring means STAFF salaries
#     and MEMBERSHIP MONTHLY dues — the same shape, one period per ACTIVE
#     month. MEMBERSHIP TERM is never touched: its single block installment is
#     written once at activation (_monthly_recurring_billing_job).
#   * Nightly: turn due contract_installment rows into PENDING payments
#     (_nightly_billing_job). This catches any installment whose payment could
#     not be raised at generation time — typically a missing wallet.
#   * Nightly, after that: move PENDING dues whose due date has passed to DEBT
#     (_daily_debt_job). DEBT is still owed — it only marks the due as late.
#
# Idempotent: an installment that already has a payment is filtered out in SQL
# (ContractInstallmentRepository.get_due_unbilled), and a month that already
# exists is never regenerated (UNIQUE(contract_id, period_start)). Waived
# installments and non-ACTIVE contracts are excluded too.
# ============================================

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.db.database import SessionLocal
from app.features.contract.contract_repository import ContractRepository
from app.features.contract.contract_service import (
    ContractService,
    month_bounds,
    wallet_id_for,
)
from app.features.contract_installment.contract_installment_repository import (
    ContractInstallmentRepository,
)
from app.features.payment.payment_model import PayableType, PaymentStatus
from app.features.payment.payment_repository import PaymentRepository
from app.features.payment.payment_schemas import PaymentCreate
from app.features.payment.payment_service import PaymentService

from app.utils.dateUtils import club_today

logger = logging.getLogger(__name__)


def run_nightly_billing_job():
    db: Session = SessionLocal()
    try:
        _nightly_billing_job(db)
    finally:
        db.close()


def run_daily_debt_job():
    db: Session = SessionLocal()
    try:
        _daily_debt_job(db)
    finally:
        db.close()


def _daily_debt_job(db: Session, on_date: date = None) -> int:
    """Move PENDING installment dues whose due date has passed to DEBT.

    A due starts PENDING on the day it is raised and becomes DEBT once its
    due date is behind it. Nothing about the money changes — DEBT is still
    outstanding and still counts in a wallet's totals (OUTSTANDING_STATUSES) —
    it just says "this one is late", so the UI can chase it.

    Runs after the billing job so a due raised tonight is judged against its
    own due date rather than being flipped the moment it appears. Waived
    installments and dues that have been settled are left alone.

    Returns the number of payments moved.
    """
    today = on_date or club_today()

    payments = PaymentRepository(db).get_pending_past_due(today)
    moved = 0

    for payment in payments:
        # Skip-and-log rather than raise: one bad row must not abort the sweep.
        try:
            payment.status = PaymentStatus.DEBT
            db.commit()
            moved += 1
        except Exception:
            logger.exception(
                "Could not mark payment %s as debt; skipping.", payment.id
            )
            db.rollback()
            continue

    return moved


def run_monthly_recurring_billing_job():
    db: Session = SessionLocal()
    try:
        _monthly_recurring_billing_job(db)
    finally:
        db.close()


def _monthly_recurring_billing_job(db: Session, on_date: date = None) -> int:
    """Add this month's installment + PENDING payment to every ACTIVE recurring
    contract that covers the month — STAFF salaries and MEMBERSHIP MONTHLY dues.

    Runs on the 1st, but any day works — it always targets the calendar month
    containing `on_date`, and a month that already exists is skipped
    (UNIQUE(contract_id, period_start) backs that at the DB level).

    MEMBERSHIP TERM contracts are not in the query at all, so re-running this
    can never renew a block.

    Returns the number of installments created.
    """
    today = on_date or club_today()
    month_start, month_end = month_bounds(today)

    contracts = ContractRepository(db).get_active_recurring_for_month(
        month_start, month_end
    )
    service = ContractService(db)
    created = 0

    for contract in contracts:
        # Skip-and-log rather than raise: one bad contract (e.g. a missing
        # wallet) must not abort the run for everyone else.
        try:
            if service.bill_contract_month(contract, today):
                created += 1
        except Exception:
            logger.exception(
                "Could not add the %s installment for contract %s; skipping.",
                month_start,
                contract.id,
            )
            db.rollback()
            continue

    return created


def _nightly_billing_job(db: Session, on_date: date = None) -> int:
    """Create PENDING payments for every due, unbilled, unwaived installment.

    Returns the number of payments created.
    """
    today = on_date or club_today()

    installments = ContractInstallmentRepository(db).get_due_unbilled(today)
    service = PaymentService(db)
    created = 0

    for installment in installments:
        contract = installment.contract
        if not contract:
            continue

        spec = contract.spec

        sender_wallet_id = wallet_id_for(db, contract, spec.sender_type)
        receiver_wallet_id = wallet_id_for(db, contract, spec.receiver_type)

        # Skip-and-log rather than raise: one contract with a missing wallet
        # must not abort billing for everyone else.
        if not sender_wallet_id or not receiver_wallet_id:
            logger.warning(
                "Skipping installment %s (contract %s): missing %s wallet.",
                installment.id,
                contract.id,
                "sender" if not sender_wallet_id else "receiver",
            )
            continue

        try:
            service.create(PaymentCreate(
                sender_wallet_id=sender_wallet_id,
                receiver_wallet_id=receiver_wallet_id,
                payment_type=spec.payment_type,
                amount=installment.amount,
                status=PaymentStatus.PENDING,
                description=(
                    f"{contract.contract_type.value} dues "
                    f"{installment.period_start} - {installment.period_end}"
                ),
                payable_type=PayableType.CONTRACT_INSTALLMENT,
                payable_id=installment.id,
            ))
        except Exception:
            logger.exception(
                "Could not create a payment for installment %s (contract %s); skipping.",
                installment.id,
                contract.id,
            )
            continue

        created += 1

    return created
