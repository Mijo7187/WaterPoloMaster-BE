import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import ConfigDict, Field, model_validator

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudSummarySchema,
    CrudUpdateSchema,
)
from app.features.contract.contract_schemas import ContractListResponse
from app.features.contract_installment.contract_installment_schemas import (
    ContractInstallmentListResponse,
)
from app.features.payment.payment_model import PayableType, PaymentStatus, PaymentTypeCode
from app.features.tournament.tournament_schemas import TournamentListResponse
from app.features.training.training_schemas import TrainingListResponse
from app.features.wallet.wallet_schemas import WalletResponse


class PayableContractInstallmentResponse(ContractInstallmentListResponse):
    """The `payable` shape when payable_type is contract_installment.

    Adds the parent `contract` (with its user and plan) so a due can be labelled
    with who owes it without a second call. Declared here rather than on
    ContractInstallmentListResponse because contract_schemas imports that
    module — nesting the contract there would close an import cycle.

    The nested chain is eager-loaded by the CONTRACT_INSTALLMENT entry in
    app/common/resolver/polymorphic_resolver.py — extend the fields here and
    the relations there together.
    """

    contract: Optional[ContractListResponse] = None


# Which schema serializes a resolved payable, keyed by its type. Mirrors the
# resolver's registry — adding a payable type means adding a line to both.
PAYABLE_RESPONSE_SCHEMAS = {
    PayableType.CONTRACT_INSTALLMENT: PayableContractInstallmentResponse,
    PayableType.TOURNAMENT: TournamentListResponse,
    PayableType.TRAINING: TrainingListResponse,
}


class PaymentCreate(CrudCreateSchema):
    sender_wallet_id: uuid.UUID
    receiver_wallet_id: uuid.UUID
    payment_type: PaymentTypeCode
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    status: PaymentStatus = PaymentStatus.PENDING
    description: Optional[str] = None

    # Polymorphic payable. Structural pairing is checked here; the rules about
    # WHICH payable type a given payment_type demands — and whether the target
    # row actually exists — live in PaymentService.create() against
    # PAYMENT_TYPE_SPECS, because payable_id has no DB foreign key to lean on.
    payable_type: Optional[PayableType] = None
    payable_id: Optional[int] = None

    @model_validator(mode="after")
    def _payable_pair_is_complete(self) -> "PaymentCreate":
        if (self.payable_type is None) != (self.payable_id is None):
            raise ValueError(
                "payable_type and payable_id must be provided together."
            )
        return self


class PaymentUpdate(CrudUpdateSchema):
    status: Optional[PaymentStatus] = None
    description: Optional[str] = None


class PaymentResponse(CrudResponseSchema):
    id: uuid.UUID
    sender_wallet_id: uuid.UUID
    receiver_wallet_id: uuid.UUID
    payment_type: PaymentTypeCode
    amount: Decimal
    status: PaymentStatus
    description: Optional[str] = None
    payable_type: Optional[PayableType] = None
    payable_id: Optional[int] = None
    created_at: Optional[datetime] = None
    sender_wallet: Optional[WalletResponse] = None
    receiver_wallet: Optional[WalletResponse] = None

    # Populated by the batch resolver before serialization. Typed loosely
    # because the concrete shape depends on payable_type; the validator below
    # narrows it to the right schema.
    payable: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _serialize_payable(self) -> "PaymentResponse":
        """Turn the raw resolved ORM payable into its list-schema dict.

        A payable that was never resolved, or whose target has been deleted
        (orphan), stays None — a dangling reference must not break the list.
        """
        if self.payable is None or isinstance(self.payable, dict):
            return self

        schema = PAYABLE_RESPONSE_SCHEMAS.get(self.payable_type)
        if schema is None:
            self.payable = None
            return self

        self.payable = schema.model_validate(self.payable).model_dump()
        return self


class PaymentFilters(CrudFilters):
    wallet_id: Optional[uuid.UUID] = None
    # Send with wallet_id: only payments between the two wallets, either
    # direction. The summary stays on wallet_id's side (income = received from
    # the second). Alone it just behaves like wallet_id.
    second_wallet_id: Optional[uuid.UUID] = None
    sender_wallet_id: Optional[uuid.UUID] = None
    receiver_wallet_id: Optional[uuid.UUID] = None
    payment_type: Optional[PaymentTypeCode] = None
    status: Optional[PaymentStatus] = None
    amount__gte: Optional[Decimal] = None
    amount__lte: Optional[Decimal] = None
    payable_type: Optional[PayableType] = None
    payable_id: Optional[int] = None
    # Calendar-day period on created_at, both ends inclusive — virtual filters
    # handled in PaymentRepository._apply_filter. Prefer these over the inherited
    # created_at__lte, which reads a bare date as midnight and drops that day.
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class PaymentSummary(CrudSummarySchema):
    """Totals over the filtered payment list (all pages). Always returned.

    Income/outcome are seen from: the ?wallet_id= wallet if given, else the
    caller's company wallet (ADMIN), else the clubs' side of the whole app
    (SUPER_ADMIN) — see PaymentRepository._summary_sides. Every other active
    filter (status, payment_type, created_at range, …) narrows it too.

    DEBT is split from PENDING on purpose: both are still owed
    (OUTSTANDING_STATUSES), but DEBT is the overdue part.
    """
    total_income: Decimal       # COMPLETED, received
    total_outcome: Decimal      # COMPLETED, paid out
    balance: Decimal            # total_income - total_outcome
    pending_income: Decimal     # PENDING, owed to us, not yet due
    pending_outcome: Decimal    # PENDING, owed by us, not yet due
    total_debt: Decimal         # DEBT, we owe and are overdue
    debt_receivable: Decimal    # DEBT, others owe us and are overdue
    count: int                  # rows matching the filters
