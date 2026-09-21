import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.db.database import SessionLocal
from app.features.company.company_model import Company
from app.features.payment.payment_model import PayableType, PaymentStatus, PaymentTypeCode
from app.features.payment.payment_repository import PaymentRepository
from app.features.payment.payment_schemas import PaymentCreate
from app.features.payment.payment_service import PaymentService
from app.features.training.training_model import Training, TrainingStatus

logger = logging.getLogger(__name__)


def run_nightly_training_job():
    db: Session = SessionLocal()
    try:
        _nightly_training_job(db)
    finally:
        db.close()


def _nightly_training_job(db: Session) -> None:
    now = datetime.now()
    today = now.date()

    # Step 1 — mark all past non-cancelled trainings as FINISHED
    trainings_raw = (
        db.query(Training)
        .filter(
            Training.training_date <= today,
            Training.status != TrainingStatus.CANCELLED.value,
            Training.status != TrainingStatus.FINISHED.value,
        )
        .all()
    )

    # Only include trainings whose end_time has already passed
    trainings = [
        t for t in trainings_raw
        if datetime.combine(t.training_date, t.end_time) <= now
    ]

    for training in trainings:
        training.status = TrainingStatus.FINISHED.value

    # Committed on its own: payment creation below goes through PaymentService,
    # whose repository commits per row, so the status changes must be durable
    # first rather than riding along on the first payment's transaction.
    db.commit()

    # Step 2 — create PENDING payments for ALL finished past trainings (not just newly marked ones)
    all_finished = (
        db.query(Training)
        .filter(
            Training.training_date <= today,
            Training.status == TrainingStatus.FINISHED.value,
        )
        .all()
    )

    # Trainings that already have a payment row — skip those
    already_paid = PaymentRepository(db).paid_payable_ids(PayableType.TRAINING)

    service = PaymentService(db)

    for training in all_finished:
        if training.id in already_paid:
            continue

        if not training.company_id or not training.pool_id:
            continue

        # Resolve wallets via company rows
        club = db.get(Company, training.company_id)
        pool = db.get(Company, training.pool_id)

        if not club or not club.w_id:
            continue
        if not pool or not pool.w_id:
            continue

        # Skip-and-log rather than raise: one unbillable training must not
        # abort the whole nightly batch.
        try:
            service.create(PaymentCreate(
                sender_wallet_id=club.w_id,
                receiver_wallet_id=pool.w_id,
                payment_type=PaymentTypeCode.CLUB_TRAINING_POOL,
                amount=training.price,
                status=PaymentStatus.PENDING,
                description=f"Training payment for {training.training_date}",
                payable_type=PayableType.TRAINING,
                payable_id=training.id,
            ))
        except Exception:
            logger.exception(
                "Could not create a '%s' payment for training %s (%s); skipping.",
                PaymentTypeCode.CLUB_TRAINING_POOL.value,
                training.id,
                training.training_date,
            )
            continue

        already_paid.add(training.id)
