# ============================================
# CONTRACT SERVICE - Business Logic
# ============================================

import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudHooks
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.features.contract.contract_model import (
    Contract,
    ContractStatus,
    ContractType,
)
from app.features.contract.contract_repository import ContractRepository
from app.features.contract_installment.contract_installment_model import (
    ContractInstallment,
)
from app.features.contract_installment.contract_installment_repository import (
    ContractInstallmentRepository,
)
from app.features.membership.membership_model import Membership
from app.features.company.company_model import Company
from app.features.users.users_models import User, UserRole
from app.features.wallet.wallet_model import WalletOwnerType
from app.utils.dateUtils import club_today


def _add_months(d: date, months: int) -> date:
    """Shift a date by whole months, clamping the day to the target month's length."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def month_bounds(on_date: date) -> Tuple[date, date]:
    """The calendar month containing `on_date` — a STAFF salary period."""
    first = on_date.replace(day=1)
    last = on_date.replace(day=calendar.monthrange(on_date.year, on_date.month)[1])
    return first, last


def generate_membership_installments(
    total: Decimal, months_count: int, installments_count: int, term_start: date
) -> List[dict]:
    """Split one term's TOTAL into `installments_count` equal installments.

    Only used to seed `installments_list` from a catalog plan when the caller
    sent none. Returns installments_list entries; due_date is always the
    period start — every installment is billed up front.

    The plan's installments_count is validated to divide its term evenly (see
    divides_term_evenly), so every sub-period is a whole number of months. The
    last installment absorbs any rounding remainder, so the amounts always sum
    back to exactly `total`.
    """
    count = installments_count or 1
    months_each = months_count // count

    total = Decimal(total)
    base = (total / count).quantize(Decimal("0.01"))

    installments: List[dict] = []
    period_start = term_start
    for index in range(count):
        period_end = _add_months(period_start, months_each) - timedelta(days=1)
        amount = base if index < count - 1 else total - base * (count - 1)
        installments.append({
            "period_start": period_start,
            "period_end": period_end,
            "due_date": period_start,
            "amount": amount,
            "waived": False,
        })
        period_start = period_end + timedelta(days=1)

    return installments


def compute_contract_status(
    start_date: date,
    end_date: Optional[date],
    today: date,
    current_status=None,
) -> ContractStatus:
    """The status a contract's dates imply on `today` (the club's local date).

    - CANCELLED is sticky: once cancelled, always cancelled.
    - start_date after today                      → DRAFT
    - start_date today or earlier, no end_date    → ACTIVE
    - start_date today or earlier, end_date today+ → ACTIVE
    - start_date and end_date both before today   → ENDED

    Pure — the single source of truth for create, update, /activate (a manual
    refresh) and the daily status job.
    """
    if current_status is not None and ContractStatus(current_status) == ContractStatus.CANCELLED:
        return ContractStatus.CANCELLED
    if start_date > today:
        return ContractStatus.DRAFT
    if end_date is None or end_date >= today:
        return ContractStatus.ACTIVE
    return ContractStatus.ENDED


def _apply_membership_defaults(data: dict, db) -> dict:
    """Build installments_list from the catalog plan when the caller sent none.

    This runs ONCE, at create. After it the contract is self-contained: the
    numbers are its own, so editing or retiring the membership later cannot
    move an already-signed contract. Explicit values always beat the plan —
    a negotiated discount is just an `amount` sent alongside the plan id (the
    plan is split over it), and a custom schedule is just an installments_list.
    """
    membership_id = data.get("membership_id")
    if membership_id is None:
        return data

    membership = db.get(Membership, membership_id)
    if not membership:
        raise NotFoundException("Membership not found")

    if membership.company_id != data.get("company_id"):
        raise ValidationException(
            ["membership_id"],
            "The membership belongs to a different company than the contract.",
        )

    if data.get("installments_list"):
        # A custom schedule — amount (if omitted) is its sum, not the plan's.
        return data

    if data.get("start_date") is None:
        raise ValidationException(
            ["start_date"],
            "start_date is required to split a membership plan into installments.",
        )

    if data.get("amount") is None:
        data["amount"] = Decimal(membership.price_month) * membership.months_count
    data["installments_list"] = generate_membership_installments(
        data["amount"],
        membership.months_count,
        membership.installments_count,
        data["start_date"],
    )

    return data


def _validate_membership_create(data: dict) -> dict:
    """MEMBERSHIP create: the installment rows are the contract.

    Rows: at least one; period_start <= period_end; sorted by period_start
    and non-overlapping. amount / start_date / end_date must equal the sum /
    first period_start / last period_end — derived when omitted.
    """
    items = data.get("installments_list") or []
    if not items:
        raise ValidationException(
            ["installments_list"],
            "A MEMBERSHIP contract needs at least one installment "
            "(a scholarship is one installment with amount 0).",
        )

    errors = []
    for index, item in enumerate(items):
        if item["period_end"] < item["period_start"]:
            errors.append((
                ["installments_list", index, "period_end"],
                "period_end must be on or after period_start.",
            ))
        if index > 0 and item["period_start"] <= items[index - 1]["period_end"]:
            errors.append((
                ["installments_list", index, "period_start"],
                "Installments must be sorted by period_start and must not "
                "overlap — this one starts on or before the previous one ends.",
            ))
    if errors:
        raise ValidationException(errors=errors)

    total = sum(
        (Decimal(item["amount"]) for item in items), Decimal("0")
    ).quantize(Decimal("0.01"))
    first_start = items[0]["period_start"]
    last_end = items[-1]["period_end"]

    if data.get("amount") is None:
        data["amount"] = total
    elif Decimal(data["amount"]) != total:
        errors.append((
            ["amount"],
            f"amount must equal the sum of installments_list ({total}).",
        ))

    if data.get("start_date") is None:
        data["start_date"] = first_start
    elif data["start_date"] != first_start:
        errors.append((
            ["start_date"],
            f"start_date must equal the first installment's period_start ({first_start}).",
        ))

    if data.get("end_date") is None:
        data["end_date"] = last_end
    elif data["end_date"] != last_end:
        errors.append((
            ["end_date"],
            f"end_date must equal the last installment's period_end ({last_end}).",
        ))

    if errors:
        raise ValidationException(errors=errors)
    return data


def _validate_staff_create(data: dict) -> dict:
    """STAFF create: a monthly salary — amount, start_date, optional end_date.

    No installments_list (the monthly salary job generates them) and no
    membership_id (a salary is never sold from the catalog).
    """
    errors = []
    if data.get("installments_list"):
        errors.append((
            ["installments_list"],
            "A STAFF contract takes no installments_list — its monthly "
            "installments are generated by the salary job.",
        ))
    if data.get("membership_id") is not None:
        errors.append((
            ["membership_id"],
            "membership_id is only valid on a MEMBERSHIP contract.",
        ))
    if data.get("amount") is None or Decimal(data["amount"]) <= 0:
        errors.append((["amount"], "A STAFF contract requires an amount > 0."))
    if data.get("start_date") is None:
        errors.append((["start_date"], "A STAFF contract requires a start_date."))
    elif data.get("end_date") is not None and data["end_date"] < data["start_date"]:
        errors.append((["end_date"], "end_date must be on or after start_date."))

    if errors:
        raise ValidationException(errors=errors)
    return data


def wallet_id_for(db: Session, contract: Contract, owner_type: WalletOwnerType):
    """The wallet on the given side of a contract.

    Direction comes from CONTRACT_TYPE_SPECS — MEMBERSHIP flows user→club,
    STAFF flows club→user — so the same lookup serves both.
    """
    if owner_type == WalletOwnerType.USER:
        user = db.get(User, contract.user_id)
        return user.w_id if user else None

    company = db.get(Company, contract.company_id)
    return company.w_id if company else None


def _is_ended(status) -> bool:
    return status is not None and ContractStatus(status) == ContractStatus.ENDED


def _require_wallets_if_ending(status, user_id: int, company_id: int, db) -> None:
    """Refuse to END a contract whose payments could not be raised.

    Runs BEFORE the save: the repository commits before post hooks run, so a
    missing wallet discovered in the post hook would leave the contract ENDED
    with nothing billed. Both sides need a wallet whatever the direction.
    """
    if not _is_ended(status):
        return

    user = db.get(User, user_id)
    if not user or not user.w_id:
        raise BadRequestException(
            "Cannot end the contract: the user has no wallet to bill against."
        )

    company = db.get(Company, company_id)
    if not company or not company.w_id:
        raise BadRequestException(
            "Cannot end the contract: the company has no wallet to bill against."
        )


def _contract_pre_create(data: dict, db, current_user: Optional[User] = None) -> dict:
    if data.get("status") is not None and (
        ContractStatus(data["status"]) == ContractStatus.CANCELLED
    ):
        raise ValidationException(
            ["status"], "A contract cannot be created as CANCELLED."
        )

    if ContractType(data.get("contract_type")) == ContractType.STAFF:
        data = _validate_staff_create(data)
    else:
        data = _apply_membership_defaults(data, db)
        data = _validate_membership_create(data)

    user = db.get(User, data.get("user_id"))
    if not user:
        raise NotFoundException("User not found")

    # Whatever the client sent, the status comes from the dates.
    data["status"] = compute_contract_status(
        data["start_date"], data.get("end_date"), club_today()
    )

    _require_wallets_if_ending(
        data["status"], data.get("user_id"), data.get("company_id"), db
    )

    return data


def _validate_membership_update(existing: Contract, data: dict) -> None:
    """MEMBERSHIP amount / end_date are the schedule's — they may be sent only
    if they still match it. Change the schedule via /contract-installment."""
    rows = sorted(existing.installments, key=lambda r: r.period_start)
    total = sum((Decimal(r.amount) for r in rows), Decimal("0")).quantize(Decimal("0.01"))
    last_end = rows[-1].period_end if rows else existing.end_date

    errors = []
    if "amount" in data and (
        data["amount"] is None or Decimal(data["amount"]) != total
    ):
        errors.append((
            ["amount"],
            f"A MEMBERSHIP amount is the sum of its installments ({total}); "
            f"edit the installments instead.",
        ))
    if "end_date" in data and data["end_date"] != last_end:
        errors.append((
            ["end_date"],
            f"A MEMBERSHIP end_date is its last installment's period_end "
            f"({last_end}); edit the installments instead.",
        ))
    if errors:
        raise ValidationException(errors=errors)


def _validate_staff_update(existing: Contract, data: dict) -> None:
    errors = []
    if "amount" in data and (
        data["amount"] is None or Decimal(data["amount"]) <= 0
    ):
        errors.append((["amount"], "A STAFF contract requires an amount > 0."))
    end = data.get("end_date", existing.end_date)
    if end is not None and end < existing.start_date:
        errors.append((["end_date"], "end_date must be on or after start_date."))
    if errors:
        raise ValidationException(errors=errors)


def _contract_pre_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """
    Row-level authorization: a non-SUPER_ADMIN user may only update contracts
    belonging to their own company. SUPER_ADMIN bypasses this check.

    When current_user is None the call is internal (test, script, background
    job) and this hook does not gate it.

    Status: a client-sent CANCELLED is accepted (and sticks forever); any
    other client-sent status is dropped. The stored status is always
    recomputed from the (possibly new) end_date.
    """
    existing = db.get(Contract, obj_id)

    if current_user is not None and UserRole.SUPER_ADMIN.value not in (
        current_user.roles or []
    ):
        if existing and existing.company_id != current_user.company_id:
            raise ForbiddenException(
                "You can only edit contracts in your own company."
            )

    if not existing:
        return data

    if ContractType(existing.contract_type) == ContractType.MEMBERSHIP:
        _validate_membership_update(existing, data)
    else:
        _validate_staff_update(existing, data)

    requested = data.pop("status", None)
    cancelled = (
        requested is not None
        and ContractStatus(requested) == ContractStatus.CANCELLED
    ) or ContractStatus(existing.status) == ContractStatus.CANCELLED

    data["status"] = compute_contract_status(
        existing.start_date,
        data.get("end_date", existing.end_date),
        club_today(),
        ContractStatus.CANCELLED if cancelled else None,
    )

    _require_wallets_if_ending(
        data["status"], existing.user_id, existing.company_id, db
    )

    return data


def _contract_post_save(obj: Contract, db, current_user: Optional[User] = None) -> None:
    """post_create / post_update: act on the computed status.

    ACTIVE STAFF gets the current month's salary installment (a mid-month
    hire is not skipped until the next 1st). ENDED is settled immediately.
    Both are idempotent, so re-saving raises nothing new.
    """
    ContractService(db).apply_status_effects(obj, club_today())


class ContractService(CrudService[Contract]):
    def __init__(self, db: Session):
        super().__init__(
            db,
            ContractRepository(db),
            hooks=CrudHooks(
                pre_create=_contract_pre_create,
                post_create=_contract_post_save,
                pre_update=_contract_pre_update,
                post_update=_contract_post_save,
            ),
        )

    # ------------------------------------------------------------------
    # Reads — ContractResponse.installments carry their payment state
    # ------------------------------------------------------------------

    def _with_payment_state(self, contract: Contract) -> Contract:
        """Attach paid_amount / payment_status to the contract's installments
        (one grouped query), so ContractResponse reports them truthfully."""
        from app.features.contract_installment.contract_installment_service import (
            ContractInstallmentService,
        )

        ContractInstallmentService(self.db).attach_payment_state(
            list(contract.installments)
        )
        return contract

    def get_by_id(self, obj_id: int, company_id: Optional[int] = None) -> Contract:
        return self._with_payment_state(super().get_by_id(obj_id, company_id=company_id))

    def update(self, obj_id: int, schema, current_user: Optional[User] = None) -> Contract:
        return self._with_payment_state(
            super().update(obj_id, schema, current_user=current_user)
        )

    # ------------------------------------------------------------------
    # Status — derived from the dates, never from the client
    # ------------------------------------------------------------------

    def activate(self, contract_id: int, current_user: Optional[User] = None) -> Contract:
        """
        Manual status refresh (the /activate endpoint).

        Status is computed from the dates on every save and moved daily by
        the status job, so this only recomputes it NOW — useful if a stored
        status looks stale. It never generates MEMBERSHIP installments (they
        are written at create). A CANCELLED contract stays CANCELLED.
        """
        contract = self.db.get(Contract, contract_id)
        if not contract:
            raise NotFoundException("Contract not found")

        if current_user is not None and UserRole.SUPER_ADMIN.value not in (
            current_user.roles or []
        ):
            if contract.company_id != current_user.company_id:
                raise ForbiddenException(
                    "You can only activate contracts in your own company."
                )

        self.refresh_status(contract, club_today())
        self.db.refresh(contract)
        return self._with_payment_state(contract)

    def refresh_status(self, contract: Contract, today: date) -> bool:
        """Store the status the dates imply on `today`, then act on it.

        Returns True if the stored status changed. Moving to ENDED needs
        both wallets (the leftovers are billed right away) — without them it
        raises and nothing is saved, so the daily job retries tomorrow.
        """
        new_status = compute_contract_status(
            contract.start_date, contract.end_date, today, contract.status
        )
        changed = new_status != ContractStatus(contract.status)

        if changed:
            _require_wallets_if_ending(
                new_status, contract.user_id, contract.company_id, self.db
            )
            contract.status = new_status
            self.db.commit()

        self.apply_status_effects(contract, today)
        return changed

    def apply_status_effects(self, contract: Contract, today: date) -> None:
        """ACTIVE STAFF → this month's salary installment; ENDED → bill leftovers."""
        status = ContractStatus(contract.status)
        if (
            status == ContractStatus.ACTIVE
            and ContractType(contract.contract_type) == ContractType.STAFF
        ):
            if self._add_staff_month(contract, today) is not None:
                self.db.commit()
        elif status == ContractStatus.ENDED:
            self.bill_ended(contract)

    def sync_from_installments(self, contract: Contract) -> None:
        """Re-derive a MEMBERSHIP contract's amount / start_date / end_date from
        its installment rows, then its status. Called by the contract-installment
        service after a single installment is created, edited or deleted.

        STAFF is left alone — its amount is the monthly salary, not a sum.
        """
        if ContractType(contract.contract_type) != ContractType.MEMBERSHIP:
            return

        rows = (
            self.db.query(ContractInstallment)
            .filter(ContractInstallment.contract_id == contract.id)
            .order_by(ContractInstallment.period_start)
            .all()
        )
        if not rows:
            return

        contract.amount = sum(
            (Decimal(r.amount) for r in rows), Decimal("0")
        ).quantize(Decimal("0.01"))
        contract.start_date = rows[0].period_start
        contract.end_date = rows[-1].period_end
        self.db.commit()

        self.refresh_status(contract, club_today())

    # ------------------------------------------------------------------
    # STAFF — one calendar-month salary installment at a time
    # ------------------------------------------------------------------

    def _add_staff_month(
        self, contract: Contract, on_date: date
    ) -> Optional[ContractInstallment]:
        """Add the salary installment for the month containing `on_date`.

        period_start = 1st of the month, period_end = its last day, amount =
        contract.amount, due on the 1st. Returns the new row, or None when the
        contract does not cover that month or the month already exists.
        Adds only — no commit.
        """
        month_start, month_end = month_bounds(on_date)

        if contract.start_date > month_end:
            return None
        if contract.end_date and contract.end_date < month_start:
            return None

        exists = (
            self.db.query(ContractInstallment.id)
            .filter(
                ContractInstallment.contract_id == contract.id,
                ContractInstallment.period_start == month_start,
            )
            .first()
        )
        if exists:
            return None

        installment = ContractInstallment(
            contract_id=contract.id,
            period_start=month_start,
            period_end=month_end,
            due_date=month_start,
            amount=Decimal(contract.amount),
            waived=False,
        )
        self.db.add(installment)
        return installment

    def bill_staff_month(self, contract: Contract, on_date: date) -> bool:
        """Monthly salary job, one contract: add this month's installment and
        raise its PENDING payment in one go. Returns True if a month was added.

        Only a contract ACTIVE on `on_date` (by its dates, not just its stored
        status) is paid. Idempotent — a month that already has an installment
        is left alone. The installment is committed BEFORE the payment, so if
        the payment cannot be raised (e.g. a missing wallet) the month is
        still owed and the nightly job bills it once it can.
        """
        if compute_contract_status(
            contract.start_date, contract.end_date, on_date, contract.status
        ) != ContractStatus.ACTIVE:
            return False

        installment = self._add_staff_month(contract, on_date)
        if installment is None:
            return False

        self.db.commit()
        self._raise_payment(contract, installment)
        return True

    def _raise_payment(
        self, contract: Contract, installment: ContractInstallment
    ) -> None:
        """Create the PENDING payment for one installment, in the contract's direction."""
        # Imported here: payment_service pulls in schemas that sit close to the
        # contract feature, and a module-level import risks a cycle.
        from app.features.payment.payment_model import PayableType, PaymentStatus
        from app.features.payment.payment_schemas import PaymentCreate
        from app.features.payment.payment_service import PaymentService

        spec = contract.spec
        sender_wallet_id = wallet_id_for(self.db, contract, spec.sender_type)
        receiver_wallet_id = wallet_id_for(self.db, contract, spec.receiver_type)
        if not sender_wallet_id or not receiver_wallet_id:
            raise BadRequestException(
                f"Contract {contract.id} is missing a wallet; cannot bill it."
            )

        PaymentService(self.db).create(PaymentCreate(
            sender_wallet_id=sender_wallet_id,
            receiver_wallet_id=receiver_wallet_id,
            payment_type=spec.payment_type,
            amount=installment.amount,
            status=PaymentStatus.PENDING,
            description=(
                f"{ContractType(contract.contract_type).value} dues "
                f"{installment.period_start} - {installment.period_end}"
            ),
            payable_type=PayableType.CONTRACT_INSTALLMENT,
            payable_id=installment.id,
        ))

    # ------------------------------------------------------------------
    # Ending — settle whatever is left
    # ------------------------------------------------------------------

    def bill_ended(self, contract: Contract) -> int:
        """
        Raise a PENDING payment for every unwaived, unbilled installment of an
        ENDED contract — future due dates included, so the contract is settled
        in one go. Returns how many payments it created.

        Idempotent: installments that already have a payment are skipped. The
        nightly job only bills ACTIVE contracts, so nothing is double-billed.
        """
        created = 0
        unbilled = ContractInstallmentRepository(self.db).get_unbilled_for_contract(
            contract.id
        )
        for installment in unbilled:
            self._raise_payment(contract, installment)
            created += 1

        return created

    def delete(self, obj_id: int) -> None:
        obj = self.db.get(Contract, obj_id)
        if not obj:
            raise NotFoundException("Contract not found")
        self.db.delete(obj)
        self.db.commit()
