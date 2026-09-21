from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.scheduler.billing_jobs import (
    run_monthly_staff_salary_job,
    run_nightly_billing_job,
)
from app.scheduler.contract_jobs import run_daily_contract_status_job
from app.scheduler.training_jobs import run_nightly_training_job

# Cron times below are in the clubs' timezone, not the server's.
scheduler = BackgroundScheduler(timezone=settings.CLUB_TIMEZONE)


def init_scheduler() -> None:
    scheduler.add_job(
        run_nightly_training_job,
        CronTrigger(hour=23, minute=59),
        id="nightly_training_job",
        replace_existing=True,
    )
    # Runs after the training job so a night's status changes are already
    # committed. Both are idempotent, so ordering is a preference, not a
    # correctness requirement.
    scheduler.add_job(
        run_nightly_billing_job,
        CronTrigger(hour=0, minute=15),
        id="nightly_billing_job",
        replace_existing=True,
    )
    # Contract statuses follow their dates: DRAFT → ACTIVE → ENDED. At 00:01,
    # before the salary (00:05) and billing (00:15) jobs, so they see today's
    # statuses.
    scheduler.add_job(
        run_daily_contract_status_job,
        CronTrigger(hour=0, minute=1),
        id="daily_contract_status_job",
        replace_existing=True,
    )
    # STAFF salaries: one calendar-month installment + PENDING payment per
    # ACTIVE STAFF contract, on the 1st. Idempotent per (contract, month).
    scheduler.add_job(
        run_monthly_staff_salary_job,
        CronTrigger(day=1, hour=0, minute=5),
        id="monthly_staff_salary_job",
        replace_existing=True,
    )
    scheduler.start()
