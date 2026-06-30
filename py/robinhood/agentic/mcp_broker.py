"""Robinhood Agentic MCP broker adapter.

The concrete MCP transport is injected so the trading logic does not depend on
Codex internals or a specific MCP SDK package.
"""

from __future__ import annotations

from typing import Any, Protocol

from .broker import AccountSnapshot, Broker, OrderIntent, OrderResult, OrderReview, Position


class McpToolClient(Protocol):
    """Small protocol required by the live broker."""

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool and return its decoded payload."""


class AgenticMcpEquityBroker(Broker):
    """Broker implementation backed by Robinhood Agentic MCP equity tools."""

    def __init__(
        self,
        account_number: str,
        client: McpToolClient,
        live_trading_enabled: bool = False,
        auto_place_orders: bool = False,
        max_live_order_dollars: float = 0.0,
        max_live_orders_per_process: int = 1,
    ):
        if not account_number:
            raise ValueError("account_number is required")
        self.account_number = account_number
        self.client = client
        self.live_trading_enabled = live_trading_enabled
        self.auto_place_orders = auto_place_orders
        self.max_live_order_dollars = max_live_order_dollars
        self.max_live_orders_per_process = max_live_orders_per_process
        self._live_order_attempts = 0
        self._live_orders_submitted = 0

    def get_account_snapshot(self) -> AccountSnapshot:
        portfolio = _as_mapping(self.client.call_tool("get_portfolio", {"account_number": self.account_number}))
        positions_payload = _as_mapping(
            self.client.call_tool("get_equity_positions", {"account_number": self.account_number})
        )
        cash = _extract_float(
            portfolio,
            (
                "cash",
                "buying_power",
                "cash_available_for_withdrawal",
                "buying_power.buying_power",
                "buying_power.unleveraged_buying_power",
            ),
        )
        return AccountSnapshot(
            cash=cash,
            positions=_extract_positions(positions_payload),
        )

    def review_order(self, intent: OrderIntent, price: float) -> OrderReview:
        tradability = self.client.call_tool(
            "get_equity_tradability",
            {
                "account_number": self.account_number,
                "symbols": [intent.symbol],
            },
        )
        tradability_alerts = _tradability_alerts(tradability, intent.symbol)
        if tradability_alerts:
            return OrderReview(
                intent=intent,
                approved=False,
                reason="equity is not tradable",
                alerts=tuple(tradability_alerts),
                raw=tradability,
            )

        payload = self.client.call_tool("review_equity_order", self._order_arguments(intent))
        review = _as_mapping(payload)
        alerts = tuple(_extract_alerts(review))
        approved = not _has_blocking_alert(alerts, review)
        return OrderReview(
            intent=intent,
            approved=approved,
            reason="mcp review approved" if approved else "mcp review blocked",
            estimated_price=_extract_optional_float(review, ("last_trade_price", "price", "estimated_price")),
            estimated_quantity=_extract_optional_float(review, ("quantity", "estimated_quantity", "estimated_shares")),
            estimated_cost=_extract_optional_float(review, ("estimated_cost", "notional", "dollar_amount")),
            alerts=alerts,
            raw=payload,
        )

    def place_order(self, intent: OrderIntent, price: float) -> OrderResult:
        review = self.review_order(intent, price)
        if not review.approved:
            return OrderResult(
                intent=intent,
                placed=False,
                status="rejected",
                reason=review.reason,
                raw=review.raw,
            )

        if not (self.live_trading_enabled and self.auto_place_orders):
            return OrderResult(
                intent=intent,
                placed=False,
                status="reviewed",
                reason="live order placement disabled",
                raw=review.raw,
            )

        live_cap_reason = self._live_order_cap_reason(intent, price)
        if live_cap_reason:
            return OrderResult(
                intent=intent,
                placed=False,
                status="rejected",
                reason=live_cap_reason,
                raw=review.raw,
            )

        fuse_reason = self._live_order_fuse_reason()
        if fuse_reason:
            return OrderResult(
                intent=intent,
                placed=False,
                status="rejected",
                reason=fuse_reason,
                raw=review.raw,
            )

        self._live_order_attempts += 1
        payload = self.client.call_tool("place_equity_order", self._order_arguments(intent, include_ref_id=True))
        result = _as_mapping(payload)
        placement_error = _placement_error_reason(result)
        if placement_error:
            return OrderResult(
                intent=intent,
                placed=False,
                status="rejected",
                reason=placement_error,
                raw=payload,
            )
        order_id = _extract_order_id(result)
        if not order_id:
            return OrderResult(
                intent=intent,
                placed=False,
                status="unconfirmed",
                reason=f"mcp order submission unconfirmed: missing order id ({_payload_summary(result)})",
                order_id="",
                filled_quantity=_extract_float(result, ("filled_quantity", "executed_quantity", "quantity")),
                average_price=_extract_float(result, ("average_price", "price")),
                raw=payload,
            )

        self._live_orders_submitted += 1
        return OrderResult(
            intent=intent,
            placed=True,
            status=_extract_order_status(result),
            reason="mcp order submitted",
            order_id=order_id,
            filled_quantity=_extract_float(result, ("filled_quantity", "executed_quantity", "quantity")),
            average_price=_extract_float(result, ("average_price", "price")),
            raw=payload,
        )

    def _order_arguments(self, intent: OrderIntent, include_ref_id: bool = False) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "account_number": self.account_number,
            "symbol": intent.symbol,
            "side": intent.side,
            "type": intent.order_type,
            "market_hours": intent.market_hours,
            "time_in_force": intent.time_in_force,
        }
        if intent.dollar_amount is not None:
            arguments["dollar_amount"] = f"{intent.dollar_amount:.2f}"
        if intent.quantity is not None:
            arguments["quantity"] = f"{intent.quantity:.6f}".rstrip("0").rstrip(".")
        if intent.limit_price is not None:
            arguments["limit_price"] = f"{intent.limit_price:.2f}"
        if include_ref_id:
            arguments["ref_id"] = intent.ref_id
        return arguments

    def _live_order_cap_reason(self, intent: OrderIntent, price: float) -> str:
        if self.max_live_order_dollars <= 0:
            return ""

        dollars = intent.dollar_amount
        if dollars is None and intent.quantity is not None:
            dollars = intent.quantity * price
        if dollars is None:
            return ""
        if dollars > self.max_live_order_dollars:
            return f"live order exceeds max_live_order_dollars (${dollars:.2f} > ${self.max_live_order_dollars:.2f})"
        return ""

    def _live_order_fuse_reason(self) -> str:
        if self.max_live_orders_per_process <= 0:
            return "max_live_orders_per_process must be greater than 0"
        if self._live_order_attempts >= self.max_live_orders_per_process:
            return (
                f"live order fuse tripped "
                f"({self._live_order_attempts}/{self.max_live_orders_per_process} attempted, "
                f"{self._live_orders_submitted} submitted)"
            )
        return ""


def _extract_order_id(payload: dict[str, Any]) -> str:
    return str(_first_matching_key(payload, ("id", "order_id", "equity_order_id", "client_order_id")) or "")


def _extract_order_status(payload: dict[str, Any]) -> str:
    return str(_first_matching_key(payload, ("state", "status")) or "submitted")


def _first_matching_key(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        for key in keys:
            found = value.get(key)
            if found not in (None, ""):
                return found
        for key in (
            "order",
            "equity_order",
            "equity_order_result",
            "result",
            "data",
            "payload",
            "results",
            "orders",
        ):
            found = _first_matching_key(value.get(key), keys)
            if found not in (None, ""):
                return found
        for found in (_first_matching_key(item, keys) for item in value.values()):
            if found not in (None, ""):
                return found
    if isinstance(value, list):
        for item in value:
            found = _first_matching_key(item, keys)
            if found not in (None, ""):
                return found
    return None


def _placement_error_reason(payload: dict[str, Any]) -> str:
    state = str(_get_path(payload, "state") or _get_path(payload, "status") or "").lower()
    alerts = _extract_alerts(payload)
    message = str(
        _get_path(payload, "message")
        or _get_path(payload, "error")
        or _get_path(payload, "error.message")
        or _get_path(payload, "detail")
        or ""
    )
    if payload.get("is_error"):
        return f"mcp order submission rejected: {_compact_reason(message, alerts, state)}"
    if state in {"rejected", "blocked", "error", "failed"}:
        return f"mcp order submission rejected: {_compact_reason(message, alerts, state)}"
    if alerts and _has_blocking_alert(tuple(alerts), payload):
        return f"mcp order submission rejected: {_compact_reason(message, alerts, state)}"
    return ""


def _compact_reason(message: str, alerts: list[str], state: str) -> str:
    reason_parts = []
    if state:
        reason_parts.append(f"state={state}")
    if message:
        reason_parts.append(message)
    reason_parts.extend(alerts[:3])
    return "; ".join(reason_parts) if reason_parts else "no order id returned"


def _payload_summary(payload: dict[str, Any]) -> str:
    if not payload:
        return "empty payload"
    keys = ",".join(sorted(str(key) for key in payload.keys())[:8])
    state = _get_path(payload, "state") or _get_path(payload, "status") or "-"
    message = _get_path(payload, "message") or _get_path(payload, "error.message") or _get_path(payload, "error") or "-"
    return f"keys={keys or '-'} state={state} message={message}"


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        data = value.get("data")
        if isinstance(data, dict):
            return data
        return value
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0]
    if isinstance(value, str):
        return {"error": value}
    return {}


def _extract_float(payload: dict[str, Any], keys: tuple[str, ...]) -> float:
    value = _extract_optional_float(payload, keys)
    return value if value is not None else 0.0


def _extract_optional_float(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _get_path(payload, key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _get_path(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _extract_positions(payload: dict[str, Any]) -> dict[str, Position]:
    raw_positions = payload.get("results") or payload.get("positions") or []
    positions: dict[str, Position] = {}
    if not isinstance(raw_positions, list):
        return positions

    for raw in raw_positions:
        if not isinstance(raw, dict):
            continue
        symbol = str(raw.get("symbol") or raw.get("instrument_symbol") or "").upper()
        if not symbol:
            continue
        quantity = _extract_float(raw, ("quantity", "shares", "total_quantity"))
        if quantity <= 0:
            continue
        average_cost = _extract_float(raw, ("average_cost", "average_buy_price", "avg_cost"))
        positions[symbol] = Position(symbol=symbol, quantity=quantity, average_cost=average_cost)
    return positions


def _tradability_alerts(payload: Any, symbol: str) -> list[str]:
    data = _as_mapping(payload)
    entries = data.get("results") or data.get("symbols") or []
    if isinstance(entries, dict):
        entries = [entries.get(symbol.upper(), {})]
    if not isinstance(entries, list):
        return []

    alerts: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("symbol", symbol)).upper() != symbol.upper():
            continue
        for key in ("tradable", "regular_hours_tradable", "fractional_tradable"):
            if entry.get(key) is False:
                alerts.append(f"{symbol.upper()} {key}=false")
    return alerts


def _extract_alerts(payload: dict[str, Any]) -> list[str]:
    raw_alerts = payload.get("alerts") or payload.get("pre_trade_alerts") or payload.get("warnings") or []
    if isinstance(raw_alerts, str):
        return [raw_alerts]
    if not isinstance(raw_alerts, list):
        return []
    alerts: list[str] = []
    for alert in raw_alerts:
        if isinstance(alert, str):
            alerts.append(alert)
        elif isinstance(alert, dict):
            alerts.append(str(alert.get("message") or alert.get("reason") or alert))
    return alerts


def _has_blocking_alert(alerts: tuple[str, ...], payload: dict[str, Any]) -> bool:
    state = str(payload.get("status") or payload.get("state") or "").lower()
    if state in {"rejected", "blocked", "error", "failed"}:
        return True
    blocking_words = ("blocked", "reject", "halt", "insufficient", "not eligible", "pdt")
    return any(any(word in alert.lower() for word in blocking_words) for alert in alerts)
