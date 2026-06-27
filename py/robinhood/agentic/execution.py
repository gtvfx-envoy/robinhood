"""Convert strategy decisions into broker order intents."""

from __future__ import annotations

from dataclasses import dataclass

from .broker import AccountSnapshot, OrderIntent
from .config import RiskConfig
from .strategy import Decision


@dataclass(frozen=True)
class ExecutionPlan:
    approved: bool
    reason: str
    intent: OrderIntent | None = None


def plan_order_intent(
    decision: Decision,
    snapshot: AccountSnapshot,
    risk: RiskConfig,
    price: float,
) -> ExecutionPlan:
    """Turn a risk-approved strategy decision into a broker intent."""

    symbol = decision.symbol.upper()
    if not decision.is_trade:
        return ExecutionPlan(False, "no trade requested")
    if price <= 0:
        return ExecutionPlan(False, "price must be positive")

    if decision.action == "BUY":
        if symbol in snapshot.positions and snapshot.positions[symbol].is_open:
            return ExecutionPlan(False, f"{symbol} position already open")
        if _open_position_count(snapshot) >= risk.max_open_positions:
            return ExecutionPlan(False, "max open positions reached")
        if risk.max_total_exposure_dollars > 0 and snapshot.equity_exposure >= risk.max_total_exposure_dollars:
            return ExecutionPlan(False, "max total exposure reached")

        exposure_room = (
            risk.max_total_exposure_dollars - snapshot.equity_exposure
            if risk.max_total_exposure_dollars > 0
            else snapshot.cash
        )
        dollars = min(
            decision.target_dollars,
            risk.max_trade_dollars,
            max(0.0, snapshot.cash - risk.min_cash_reserve),
            max(0.0, exposure_room),
        )
        if dollars < risk.min_order_dollars:
            return ExecutionPlan(False, "available dollars below minimum order size")
        return ExecutionPlan(
            True,
            "approved order intent",
            OrderIntent(
                symbol=symbol,
                side="buy",
                order_type="market",
                dollar_amount=round(dollars, 2),
                market_hours="regular_hours",
                time_in_force="gfd",
            ),
        )

    position = snapshot.positions.get(symbol)
    if position is None or not position.is_open:
        return ExecutionPlan(False, f"no open {symbol} position to sell")
    return ExecutionPlan(
        True,
        "approved order intent",
        OrderIntent(
            symbol=symbol,
            side="sell",
            order_type="market",
            quantity=round(position.quantity, 6),
            market_hours="regular_hours",
            time_in_force="gfd",
        ),
    )


def _open_position_count(snapshot: AccountSnapshot) -> int:
    return sum(1 for position in snapshot.positions.values() if position.is_open)
