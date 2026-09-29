# ============================================
# CONTRACT SERVICE - Business Logic
# ============================================

import calendar
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Tuple

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
from app.features.membership.membership_model import BillingType, Membership
from app.features.company.company_model import Company
from app.features.users.users_models import User, UserRole
from app.features.wallet.wallet_model import WalletOwnerType
from app.utils.dateUtils import club_today

logger = logging.getLogger(__name__)


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


def term_end_date(start_date: date, term_months: int) -> date:
    """The inclusive last day of a TERM block starting on `start_date`.

    3 months from 2026-09-01 ends 2026-11-30, not 2026-12-01 — the same
    inclusive convention the old installment generator used.
    """
    return _add_months(start_date, term_months) - timedelta(days=1)


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


def _snapshot_membership(data: dict, db) -> dict:
    """MEMBERSHIP create: copy the plan's terms onto the contract.

    Runs ONCE, at create. After it the contract is self-contained — the
    billing_type, the price and the term length are its own, so editing or
    retiring the membership later cannot move an already-signed contract.

    The shape of the contract follows billing_type:
      MONTHLY -> end_date is NULL. Open-ended; the recurring job bills it every
                 month until it is cancelled.
      TERM    -> end_date = start_date + term_months (inclusive). One block.
    """
    membership_id = data.get("membership_id")
    if membership_id is None:
        raise ValidationException(
            ["membership_id"],
            "A MEMBERSHIP contract requires a membership_id — its billing "
            "type, price and term are taken from the plan.",
        )

    membership = db.get(Membership, membership_id)
    if not membership:
        raise NotFoundException("Membership not found")

    # A club may sign off its academy's catalog: the academy owns the shared
    # price list and opens the groups, while the contract stays down at the club.
    company_id = data.get("company_id")
    company = db.get(Company, company_id) if company_id is not None else None
    allowed = {company_id}
    if company is not None and company.academy_id is not None:
        allowed.add(company.academy_id)

    if membership.company_id not in allowed:
        raise ValidationException(
            ["membership_id"],
            "The membership must belong to the contract's company or to its academy.",
        )

    if data.get("start_date") is None:
        raise ValidationException(
            ["start_date"], "A MEMBERSHIP contract requires a start_date."
        )

    billing_type = BillingType(membership.billing_type)
    data["billing_type"] = billing_type
    data["amount"] = Decimal(membership.price)
    data["term_months"] = membership.term_months

    if billing_type == BillingType.MONTHLY:
        derived_end = None
    else:
        derived_end = term_end_date(data["start_date"], membership.term_months)

    # The client may echo the derived end_date back, but may not contradict it.
    if data.get("end_date") is not None and data["end_date"] != derived_end:
        raise ValidationException(
            ["end_date"],
            f"A {billing_type.value} membership contract's end_date is "
            f"{derived_end} — it is derived from the plan, not sent.",
        )
    data["end_date"] = derived_end

    return data


def _validate_staff_create(data: dict) -> dict:
    """STAFF create: a monthly salary — amount, start_date, optional end_date.

    No membership_id (a salary is never sold from the catalog); its monthly
    installments come from the recurring job.
    """
    errors = []
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
        data = _snapshot_membership(data, db)

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


def _validate_contract_update(existing: Contract, data: dict) -> None:
    """The same rules for both types now that `amount` means one thing.

    `amount` is the per-installment price, so it is simply a positive number —
    it is no longer tied to the sum of the installment rows. `end_date` is
    freely settable: that is how an open-ended MONTHLY contract is closed.
    Already-generated installments are left alone; editing one no longer moves
    the contract either (see contract_installment_service).
    """
    errors = []
    if "amount" in data and (
        data["amount"] is None or Decimal(data["amount"]) <= 0
    ):
        errors.append((["amount"], "A contract requires an amount > 0."))
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

    _validate_contract_update(existing, data)

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


def _auto_enrol_in_group(obj: Contract, db) -> None:
    """Put a MEMBERSHIP contract's user in the current season's group.

    The group is (the academy's current season, the membership's selection),
    created on first use — signing the first player of a squad is what brings
    the squad into existence. The academy is the club's `academy_id`, or the
    club itself when it belongs to no academy.

    Best-effort by design: with no current season, no membership or no
    selection there is nothing to enrol into, so it is skipped and can be
    added by hand. It must never fail the contract — this runs in post_create,
    AFTER the repository has already committed the row, so raising here would
    report a failure for a contract that exists.
    """
    if ContractType(obj.contract_type) != ContractType.MEMBERSHIP:
        return
    if obj.membership_id is None:
        return

    # Imported here: the group features are peers, and a module-level import
    # risks a cycle through season / selection schemas.
    from app.features.group.group_service import GroupService
    from app.features.group_user.group_user_service import GroupUserService

    try:
        membership = db.get(Membership, obj.membership_id)
        if not membership or membership.selection_id is None:
            return

        groups = GroupService(db)
        company = groups.repository.get_company(obj.company_id)
        if company is None:
            return

        academy_id = company.academy_id or company.id
        season = groups.repository.get_current_season_for_company(academy_id)
        if season is None:
            logger.info(
                "Contract %s: no current season for academy %s; skipping the "
                "group enrolment.",
                obj.id,
                academy_id,
            )
            return

        group = groups.get_or_create(season.id, membership.selection_id)
        GroupUserService(db).enrol_if_absent(group.id, obj.user_id)
    except Exception:
        logger.exception(
            "Contract %s: could not enrol user %s in the season's group; "
            "the contract stands and the roster row can be added by hand.",
            obj.id,
            obj.user_id,
        )
        db.rollback()


def _contract_post_save(obj: Contract, db, current_user: Optional[User] = None) -> None:
    """post_create / post_update: act on the computed status, then enrol.

    An ACTIVE contract gets the period it owes right away (a mid-month signing
    is not skipped until the next 1st); ENDED is settled immediately. Both are
    idempotent, so re-saving raises nothing new.
    """
    ContractService(db).apply_status_effects(obj, club_today())
    _auto_enrol_in_group(obj, db)


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
        status looks stale. Generation is idempotent, so a contract that is
        already ACTIVE gains nothing new. A CANCELLED contract stays CANCELLED.
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
        """Act on the computed status — what a fresh or newly-ACTIVE contract owes.

            ACTIVE + STAFF               → this month's salary installment
            ACTIVE + MEMBERSHIP MONTHLY  → this month's installment + payment
            ACTIVE + MEMBERSHIP TERM     → the one block installment + payment
            ENDED                        → bill whatever is left

        A missing wallet must not fail the contract save: this runs in
        post_create / post_update, AFTER the repository has already committed
        the row, so raising here would report a failure for a contract that
        exists. The installment is written either way and the nightly billing
        job raises its payment once the wallet is there.

        MEMBERSHIP raises its payment on the spot so a player sees the charge
        the moment they sign. STAFF deliberately keeps its original behaviour —
        the row now, the payment from the recurring job — so this change does
        not move salary billing.
        """
        status = ContractStatus(contract.status)
        if status not in (ContractStatus.ACTIVE, ContractStatus.ENDED):
            return

        is_term = (
            ContractType(contract.contract_type) == ContractType.MEMBERSHIP
            and contract.billing_type is not None
            and BillingType(contract.billing_type) == BillingType.TERM
        )

        if status == ContractStatus.ENDED:
            # A TERM block is owed for its whole period, so it is written even
            # when the contract is already over — a block backdated at signing
            # still has to be billed. bill_ended then picks it up.
            if is_term and self._add_term_block(contract) is not None:
                self.db.commit()
            self.bill_ended(contract)
            return

        if ContractType(contract.contract_type) == ContractType.STAFF:
            if self._add_month(contract, today) is not None:
                self.db.commit()
            return

        try:
            if is_term:
                self.bill_term_block(contract)
            else:
                self.bill_contract_month(contract, today)
        except BadRequestException:
            logger.exception(
                "Contract %s: installment written but its payment could not be "
                "raised; the nightly billing job will retry.",
                contract.id,
            )

    # ------------------------------------------------------------------
    # Generation — one calendar month at a time, or one TERM block
    # ------------------------------------------------------------------

    def _add_month(
        self, contract: Contract, on_date: date
    ) -> Optional[ContractInstallment]:
        """Add the installment for the month containing `on_date`.

        period_start = 1st of the month, period_end = its last day, amount =
        contract.amount, due on the 1st. Returns the new row, or None when the
        contract does not cover that month or the month already exists.
        Adds only — no commit.

        Serves STAFF salaries and MEMBERSHIP MONTHLY alike: both are "one
        period of `contract.amount` per ACTIVE month".
        """
        month_start, month_end = month_bounds(on_date)

        if contract.start_date > month_end:
            return None
        if contract.end_date and contract.end_date < month_start:
            return None

        return self._add_period(contract, month_start, month_end)

    def _add_term_block(self, contract: Contract) -> Optional[ContractInstallment]:
        """Add the single installment covering a TERM contract's whole block.

        period_start = start_date, period_end = end_date, due on the start,
        amount = the block price. Returns None if it already exists.
        """
        if contract.end_date is None:
            return None
        return self._add_period(contract, contract.start_date, contract.end_date)

    def _add_period(
        self, contract: Contract, period_start: date, period_end: date
    ) -> Optional[ContractInstallment]:
        """Write one installment unless that period_start already has one.

        The existence check mirrors UNIQUE(contract_id, period_start), which
        backs idempotency at the DB level. Adds only — no commit.
        """
        exists = (
            self.db.query(ContractInstallment.id)
            .filter(
                ContractInstallment.contract_id == contract.id,
                ContractInstallment.period_start == period_start,
            )
            .first()
        )
        if exists:
            return None

        installment = ContractInstallment(
            contract_id=contract.id,
            period_start=period_start,
            period_end=period_end,
            due_date=period_start,
            amount=Decimal(contract.amount),
            waived=False,
        )
        self.db.add(installment)
        return installment

    def bill_contract_month(self, contract: Contract, on_date: date) -> bool:
        """Recurring job, one contract: add this month's installment and raise
        its PENDING payment in one go. Returns True if a month was added.

        Only a contract ACTIVE on `on_date` (by its dates, not just its stored
        status) is billed. Idempotent — a month that already has an installment
        is left alone. The installment is committed BEFORE the payment, so if
        the payment cannot be raised (e.g. a missing wallet) the month is
        still owed and the nightly job bills it once it can.

        Drives both STAFF salaries and MEMBERSHIP MONTHLY dues. TERM contracts
        never reach it.
        """
        if compute_contract_status(
            contract.start_date, contract.end_date, on_date, contract.status
        ) != ContractStatus.ACTIVE:
            return False

        installment = self._add_month(contract, on_date)
        if installment is None:
            return False

        self.db.commit()
        self._raise_payment(contract, installment)
        return True

    def bill_term_block(self, contract: Contract) -> bool:
        """A TERM contract's one-shot: the whole block as a single installment
        plus its PENDING payment. Returns True if the block was added.

        Idempotent, so re-saving or re-activating raises nothing new. The
        recurring job never calls this — re-signing for the next block is a
        new contract.
        """
        installment = self._add_term_block(contract)
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
