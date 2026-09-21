# ============================================
# POLYMORPHIC RESOLVER - Batched target lookup
# ============================================
# Going polymorphic (payment.payable_type/payable_id, wallet.owner_type/owner_id)
# means there is no relationship to selectinload. This replaces the eager-load
# chains with one batched resolution pass, shared by the payment list and the
# wallet list.
#
# Guarantees:
#   * BATCHED BY TYPE — one `WHERE id IN (...)` per distinct type, never per row.
#     Query count is bounded by the number of types, not by list size.
#   * Each type declares the nested relations its list schema needs, mirroring
#     what payment_repository._payment_relations() used to eager-load.
#   * Orphans (target deleted, referencing row remains) resolve to None. Never
#     raises — a dangling payable must not take down a whole list endpoint.
#
# Adding a new payable/owner type is a one-line addition to the registry below.
# ============================================

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Hashable, Iterable, List, Optional, Tuple, Type

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ResolverEntry:
    """How to load one type: its model, and the eager loads its schema needs."""

    model: Type[Any]
    relations: Callable[[], List[Any]] = field(default=lambda: [])


# --------------------------------------------------------------------------
# Registries. Built lazily so this module can be imported from anywhere
# without dragging every feature model in at import time.
# --------------------------------------------------------------------------

_PAYABLE_REGISTRY: Optional[Dict[Any, ResolverEntry]] = None
_WALLET_OWNER_REGISTRY: Optional[Dict[Any, ResolverEntry]] = None


def payable_registry() -> Dict[Any, ResolverEntry]:
    global _PAYABLE_REGISTRY
    if _PAYABLE_REGISTRY is None:
        from sqlalchemy.orm import selectinload

        from app.features.company.company_model import Company
        from app.features.contract.contract_model import Contract
        from app.features.contract_installment.contract_installment_model import (
            ContractInstallment,
        )
        from app.features.payment.payment_model import PayableType
        from app.features.tournament.tournament_model import Tournament
        from app.features.training.training_model import Training

        _PAYABLE_REGISTRY = {
            PayableType.CONTRACT_INSTALLMENT: ResolverEntry(
                ContractInstallment,
                lambda: [
                    selectinload(ContractInstallment.contract).selectinload(
                        Contract.user
                    ),
                ],
            ),
            PayableType.TOURNAMENT: ResolverEntry(
                Tournament,
                lambda: [
                    selectinload(Tournament.tournament_users),
                    selectinload(Tournament.company).selectinload(Company.city),
                    selectinload(Tournament.company).selectinload(Company.country),
                    selectinload(Tournament.pool).selectinload(Company.city),
                    selectinload(Tournament.pool).selectinload(Company.country),
                ],
            ),
            PayableType.TRAINING: ResolverEntry(
                Training,
                lambda: [
                    selectinload(Training.training_users),
                    selectinload(Training.company).selectinload(Company.city),
                    selectinload(Training.company).selectinload(Company.country),
                    selectinload(Training.pool).selectinload(Company.city),
                    selectinload(Training.pool).selectinload(Company.country),
                ],
            ),
        }
    return _PAYABLE_REGISTRY


def wallet_owner_registry() -> Dict[Any, ResolverEntry]:
    global _WALLET_OWNER_REGISTRY
    if _WALLET_OWNER_REGISTRY is None:
        from sqlalchemy.orm import selectinload

        from app.features.company.company_model import Company
        from app.features.users.users_models import User
        from app.features.wallet.wallet_model import WalletOwnerType

        _WALLET_OWNER_REGISTRY = {
            WalletOwnerType.USER: ResolverEntry(User),
            WalletOwnerType.COMPANY: ResolverEntry(
                Company,
                lambda: [
                    selectinload(Company.city),
                    selectinload(Company.country),
                ],
            ),
        }
    return _WALLET_OWNER_REGISTRY


def payable_model_for(payable_type) -> Optional[Type[Any]]:
    """The model class behind a payable type, or None if the type is unknown.

    Used by payment_service to verify a payable_id actually exists — the
    app-layer stand-in for the foreign key we deliberately gave up.
    """
    entry = payable_registry().get(payable_type)
    return entry.model if entry else None


class PolymorphicResolver:
    """Resolves (type, id) pairs to objects in a bounded number of queries."""

    def __init__(self, db: Session, registry: Dict[Any, ResolverEntry]):
        self.db = db
        self.registry = registry

    def resolve_batch(
        self, pairs: Iterable[Tuple[Any, Any]]
    ) -> Dict[Tuple[Hashable, Any], Any]:
        """
        Map (type, id) -> object. One query per distinct type.

        Unknown types and missing rows resolve to None rather than raising —
        callers get a placeholder, not an exception.
        """
        by_type: Dict[Any, set] = {}
        for type_key, obj_id in pairs:
            if type_key is None or obj_id is None:
                continue
            by_type.setdefault(type_key, set()).add(obj_id)

        resolved: Dict[Tuple[Hashable, Any], Any] = {}

        for type_key, ids in by_type.items():
            entry = self.registry.get(type_key)
            if entry is None:
                # Unknown type (e.g. a payable kind removed from the registry) —
                # every pair of that type resolves to None.
                continue

            q = self.db.query(entry.model)
            for opt in entry.relations():
                q = q.options(opt)

            for obj in q.filter(entry.model.id.in_(ids)).all():
                resolved[(type_key, obj.id)] = obj

        return resolved

    def attach(
        self,
        rows: List[Any],
        type_attr: str,
        id_attr: str,
        target_attr: str,
    ) -> List[Any]:
        """
        Resolve every row's target and set it on `target_attr` in place.

        Rows are ORM objects; `target_attr` must not collide with a mapped
        column. Orphans get None.
        """
        pairs = [(getattr(r, type_attr), getattr(r, id_attr)) for r in rows]
        resolved = self.resolve_batch(pairs)

        for row in rows:
            key = (getattr(row, type_attr), getattr(row, id_attr))
            setattr(row, target_attr, resolved.get(key))

        return rows


def resolve_payables(db: Session, rows: List[Any]) -> List[Any]:
    """Attach `.payable` to a list of Payment rows."""
    return PolymorphicResolver(db, payable_registry()).attach(
        rows, "payable_type", "payable_id", "payable"
    )


def resolve_wallet_owners(db: Session, rows: List[Any]) -> List[Any]:
    """Attach `.owner` to a list of Wallet rows."""
    return PolymorphicResolver(db, wallet_owner_registry()).attach(
        rows, "owner_type", "owner_id", "owner"
    )
