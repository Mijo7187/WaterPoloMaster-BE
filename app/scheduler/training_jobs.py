from datetime import date, datetime

from sqlalchemy import cast, Date, func
from sqlalchemy.orm import Session

from app.core.db.database import SessionLocal
from app.features.payment.payment_model import Payment, PaymentStatus
from app.features.sifarnici.payment_type.payment_type_model import PaymentType, PaymentTypeCode
from app.features.training.training_model import Training, TrainingStatus


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

    db.flush()

    # Step 2 — create PENDING payments for ALL finished past trainings (not just newly marked ones)
    payment_type = (
        db.query(PaymentType)
        .filter(PaymentType.code == PaymentTypeCode.CLUB_TRAINING_POOL)
        .first()
    )

    if not payment_type:
        db.commit()
        return

    all_finished = (
        db.query(Training)
        .filter(
            Training.training_date <= today,
            Training.status == TrainingStatus.FINISHED.value,
        )
        .all()
    )

    for training in all_finished:
        if not training.company_id or not training.pool_id:
            continue

        # Resolve wallets via company rows
        from app.features.company.company_model import Company
        club = db.get(Company, training.company_id)
        pool = db.get(Company, training.pool_id)

        if not club or not club.w_id:
            continue
        if not pool or not pool.w_id:
            continue

        # Duplicate guard — skip if a payment for this training date/sender/receiver/amount already exists
        existing = (
            db.query(Payment)
            .filter(
                Payment.sender_wallet_id == club.w_id,
                Payment.receiver_wallet_id == pool.w_id,
                Payment.amount == training.price,
                Payment.description == f"Training payment for {training.training_date}",
            )
            .first()
        )
        if existing:
            continue

        db.add(Payment(
            sender_wallet_id=club.w_id,
            receiver_wallet_id=pool.w_id,
            payment_type_id=payment_type.id,
            amount=training.price,
            status=PaymentStatus.PENDING,
            description=f"Training payment for {training.training_date}",
        ))

    db.commit()
