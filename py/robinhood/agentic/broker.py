"""Broker abstractions for paper and future live execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float
    average_cost: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.quantity > 0


@dataclass(frozen=True)
class AccountSnapshot:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)

    @property
    def equity_exposure(self) -> float:
        return sum(position.quantity * position.average_cost for position in self.positions.values())


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str
    order_type: str = "market"
    dollar_amount: float | None = None
    quantity: float | None = None
    limit_price: float | None = None
    market_hours: str = "regular_hours"
    time_in_force: str = "gfd"
    ref_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        normalized_side = self.side.lower()
        normalized_type = self.order_type.lower()
        if normalized_side not in {"buy", "sell"}:
            raise ValueError("order side must be buy or sell")
        if normalized_type not in {"market", "limit", "stop_market", "stop_limit"}:
            raise ValueError("unsupported order type")
        if (self.dollar_amount is None) == (self.quantity is None):
            raise ValueError("provide exactly one of dollar_amount or quantity")
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "side", normalized_side)
        object.__setattr__(self, "order_type", normalized_type)


@dataclass(frozen=True)
class OrderReview:
    intent: OrderIntent
    approved: bool
    reason: str
    estimated_price: float | None = None
    estimated_quantity: float | None = None
    estimated_cost: float | None = None
    alerts: tuple[str, ...] = ()
    raw: Any = None


@dataclass(frozen=True)
class OrderResult:
    intent: OrderIntent
    placed: bool
    status: str
    reason: str
    order_id: str = ""
    filled_quantity: float = 0.0
    average_price: float | None = None
    raw: Any = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Broker(ABC):
    """Execution boundary for paper and live account brokers."""

    @abstractmethod
    def get_account_snapshot(self) -> AccountSnapshot:
        """Return current cash and open positions."""

    @abstractmethod
    def review_order(self, intent: OrderIntent, price: float) -> OrderReview:
        """Review an order intent before placement."""

    @abstractmethod
    def place_order(self, intent: OrderIntent, price: float) -> OrderResult:
        """Place or simulate an order intent."""


class PaperBroker(Broker):
    """In-memory broker that simulates fractional equity fills."""

    def __init__(self, starting_cash: float = 100.0):
        self.cash = starting_cash
        self.positions: dict[str, Position] = {}
        self.orders: list[OrderResult] = []

    def get_account_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(cash=self.cash, positions=dict(self.positions))

    def review_order(self, intent: OrderIntent, price: float) -> OrderReview:
        if price <= 0:
            return OrderReview(intent, False, "price must be positive")

        if intent.side == "buy":
            dollars = float(intent.dollar_amount or ((intent.quantity or 0.0) * price))
            if dollars <= 0:
                return OrderReview(intent, False, "buy amount must be positive")
            if dollars > self.cash:
                return OrderReview(intent, False, "insufficient paper cash")
            return OrderReview(
                intent=intent,
                approved=True,
                reason="paper review approved",
                estimated_price=price,
                estimated_quantity=dollars / price,
                estimated_cost=dollars,
            )

        quantity = float(intent.quantity or 0.0)
        position = self.positions.get(intent.symbol)
        if quantity <= 0:
            return OrderReview(intent, False, "sell quantity must be positive")
        if position is None or position.quantity < quantity:
            return OrderReview(intent, False, "sell would exceed paper position")
        return OrderReview(
            intent=intent,
            approved=True,
            reason="paper review approved",
            estimated_price=price,
            estimated_quantity=quantity,
            estimated_cost=quantity * price,
        )

    def place_order(self, intent: OrderIntent, price: float) -> OrderResult:
        review = self.review_order(intent, price)
        if not review.approved:
            result = OrderResult(
                intent=intent,
                placed=False,
                status="rejected",
                reason=review.reason,
                raw=review,
            )
            self.orders.append(result)
            return result

        if intent.side == "buy":
            dollars = float(review.estimated_cost or 0.0)
            quantity = float(review.estimated_quantity or 0.0)
            self.cash -= dollars
            existing = self.positions.get(intent.symbol)
            if existing and existing.quantity > 0:
                total_quantity = existing.quantity + quantity
                total_cost = (existing.quantity * existing.average_cost) + dollars
                average_cost = total_cost / total_quantity
            else:
                total_quantity = quantity
                average_cost = price
            self.positions[intent.symbol] = Position(intent.symbol, total_quantity, average_cost)
            return self._record_fill(intent, quantity, price, "filled", "paper buy filled")

        quantity = float(intent.quantity or 0.0)
        existing = self.positions.get(intent.symbol)
        remaining = (existing.quantity if existing else 0.0) - quantity
        if remaining > 0 and existing:
            self.positions[intent.symbol] = Position(intent.symbol, remaining, existing.average_cost)
        else:
            self.positions.pop(intent.symbol, None)
        self.cash += quantity * price
        return self._record_fill(intent, quantity, price, "filled", "paper sell filled")

    def _record_fill(
        self,
        intent: OrderIntent,
        quantity: float,
        price: float,
        status: str,
        reason: str,
    ) -> OrderResult:
        result = OrderResult(
            intent=intent,
            placed=True,
            status=status,
            reason=reason,
            order_id=intent.ref_id,
            filled_quantity=quantity,
            average_price=price,
        )
        self.orders.append(result)
        return result
