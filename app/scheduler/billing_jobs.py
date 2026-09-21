# ============================================
# BILLING JOBS - Scheduled fee generation
# ============================================
# Two jobs:
#   * Monthly (1st of the month): every ACTIVE STAFF contract covering the
#     month gets that month's salary installment (1st - last day, amount =
#     contract.amount) and its PENDING payment (_monthly_staff_salary_job).
#   * Nightly: turn due contract_installment rows into PENDING payments
#     (_nightly_billing_job). This bills MEMBERSHIP installments — written at
#     contract create from installments_list — as each due date arrives, and
#     catches any STAFF month whose payment could not be raised.
#
# Idempotent: an installment that already has a payment is filtered out in SQL
# (ContractInstallmentRepository.get_due_unbilled), and a STAFF month that
# already exists is never regenerated. Waived installments and non-ACTIVE
# contracts are excluded too.
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


def run_monthly_staff_salary_job():
    db: Session = SessionLocal()
    try:
        _monthly_staff_salary_job(db)
    finally:
        db.close()


def _monthly_staff_salary_job(db: Session, on_date: date = None) -> int:
    """Add this month's salary installment + PENDING payment to every ACTIVE
    STAFF contract that covers the month.

    Runs on the 1st, but any day works — it always targets the calendar month
    containing `on_date`, and a month that already exists is skipped
    (UNIQUE(contract_id, period_start) backs that at the DB level).

    Returns the number of installments created.
    """
    today = on_date or club_today()
    month_start, month_end = month_bounds(today)

    contracts = ContractRepository(db).get_active_staff_for_month(
        month_start, month_end
    )
    service = ContractService(db)
    created = 0

    for contract in contracts:
        # Skip-and-log rather than raise: one bad contract (e.g. a missing
        # wallet) must not abort the salary run for everyone else.
        try:
            if service.bill_staff_month(contract, today):
                created += 1
        except Exception:
            logger.exception(
                "Could not add the %s salary for contract %s; skipping.",
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
