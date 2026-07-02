from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.training_jobs import run_nightly_training_job

scheduler = BackgroundScheduler()


def init_scheduler() -> None:
    scheduler.add_job(
        run_nightly_training_job,
        CronTrigger(hour=23, minute=59),
        id="nightly_training_job",
        replace_existing=True,
    )
    scheduler.start()
