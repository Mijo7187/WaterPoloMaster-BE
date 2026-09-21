# ============================================
# CONTRACT JOBS - Daily status roll-forward
# ============================================
# A contract's status is derived from its dates (compute_contract_status),
# but it is STORED so `?status=` list filters work. As dates pass, the stored
# value goes stale; this job moves it: DRAFT → ACTIVE → ENDED. CANCELLED is
# never touched.
#
# Runs just after midnight (club timezone), BEFORE the monthly salary job and
# the nightly billing job, so on the 1st a STAFF contract starting that day is
# ACTIVE, gets its month, and is billed — all in the same night.
#
# Moving to ACTIVE also adds a STAFF contract's current-month installment;
# moving to ENDED bills the contract's leftovers (see
# ContractService.refresh_status). Idempotent: a contract already in the
# right status is not selected.
# ============================================

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.db.database import SessionLocal
from app.features.contract.contract_repository import ContractRepository
from app.features.contract.contract_service import ContractService
from app.utils.dateUtils import club_today

logger = logging.getLogger(__name__)


def run_daily_contract_status_job():
    db: Session = SessionLocal()
    try:
        _daily_contract_status_job(db)
    finally:
        db.close()


def _daily_contract_status_job(db: Session, on_date: date = None) -> int:
    """Move every stale stored status to the one its dates imply.

    Returns the number of contracts whose status changed.
    """
    today = on_date or club_today()

    contracts = ContractRepository(db).get_stale_status(today)
    service = ContractService(db)
    changed = 0

    for contract in contracts:
        # Skip-and-log rather than raise: one contract that cannot end (e.g. a
        # missing wallet) must not block everyone else. It stays in its old
        # status and is retried tomorrow.
        try:
            if service.refresh_status(contract, today):
                changed += 1
        except Exception:
            logger.exception(
                "Could not refresh the status of contract %s; skipping.",
                contract.id,
            )
            db.rollback()
            continue

    return changed
