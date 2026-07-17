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
    """Broker implementation backed by Robinhood Agentic MCP equity and crypto tools."""

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
        crypto_positions_payload = _as_mapping(
            _safe_call_tool(self.client, "get_crypto_holdings", {"account_number": self.account_number})
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
        positions = _extract_positions(positions_payload)
        positions.update(_extract_crypto_positions(crypto_positions_payload))
        return AccountSnapshot(
            cash=cash,
            positions=positions,
        )

    def review_order(self, intent: OrderIntent, price: float) -> OrderReview:
        if intent.asset_class == "crypto":
            return self._review_crypto_order(intent, price)
        return self._review_equity_order(intent, price)

    def _review_equity_order(self, intent: OrderIntent, price: float) -> OrderReview:
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

        payload = self.client.call_tool("review_equity_order", self._order_arguments(intent, price=price))
        return self._review_from_payload(intent, payload)

    def _review_crypto_order(self, intent: OrderIntent, price: float) -> OrderReview:
        try:
            payload = self.client.call_tool("review_crypto_order", self._order_arguments(intent, price=price))
        except Exception as exc:
            return OrderReview(
                intent=intent,
                approved=False,
                reason=f"crypto MCP review failed: {exc}",
            )
        return self._review_from_payload(intent, payload)

    def _review_from_payload(self, intent: OrderIntent, payload: Any) -> OrderReview:
        review = _as_mapping(payload)
        alerts = tuple(_extract_alerts(review))
        approved = _review_is_approved(review, alerts)
        return OrderReview(
            intent=intent,
            approved=approved,
            reason="mcp review approved" if approved else "mcp review blocked",
            estimated_price=_extract_optional_float(review, ("last_trade_price", "price", "estimated_price")),
            estimated_quantity=_extract_optional_float(
                review, ("quantity", "asset_quantity", "estimated_quantity", "estimated_shares")
            ),
            estimated_cost=_extract_optional_float(review, ("estimated_cost", "notional", "quote_amount", "dollar_amount")),
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
        placement_tool = "place_crypto_order" if intent.asset_class == "crypto" else "place_equity_order"
        payload = self.client.call_tool(
            placement_tool,
            self._order_arguments(intent, price=price, include_ref_id=True),
        )
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
                filled_quantity=_extract_float(result, ("filled_quantity", "executed_quantity", "asset_quantity", "quantity")),
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
            filled_quantity=_extract_float(result, ("filled_quantity", "executed_quantity", "asset_quantity", "quantity")),
            average_price=_extract_float(result, ("average_price", "price")),
            raw=payload,
        )

    def _order_arguments(self, intent: OrderIntent, price: float = 0.0, include_ref_id: bool = False) -> dict[str, Any]:
        if intent.asset_class == "crypto":
            return self._crypto_order_arguments(intent, price=price, include_ref_id=include_ref_id)

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

    def _crypto_order_arguments(
        self,
        intent: OrderIntent,
        price: float,
        include_ref_id: bool = False,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "account_number": self.account_number,
            "symbol": _to_crypto_pair(intent.symbol),
            "side": intent.side,
            "type": intent.order_type,
        }
        quantity = intent.quantity
        if quantity is None and intent.dollar_amount is not None and price > 0:
            quantity = intent.dollar_amount / price
        if quantity is not None:
            arguments["asset_quantity"] = _format_crypto_quantity(quantity)
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
    return str(
        _first_matching_key(payload, ("id", "order_id", "equity_order_id", "crypto_order_id", "client_order_id"))
        or ""
    )


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
            "crypto_order",
            "crypto_order_result",
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


def _safe_call_tool(client: McpToolClient, name: str, arguments: dict[str, Any]) -> Any:
    try:
        return client.call_tool(name, arguments)
    except Exception as exc:
        return {"is_error": True, "error": str(exc)}


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


def _extract_crypto_positions(payload: dict[str, Any]) -> dict[str, Position]:
    if payload.get("is_error"):
        return {}
    raw_positions = payload.get("results") or payload.get("holdings") or payload.get("positions") or []
    positions: dict[str, Position] = {}
    if not isinstance(raw_positions, list):
        return positions

    for raw in raw_positions:
        if not isinstance(raw, dict):
            continue
        symbol = _crypto_asset_code(raw)
        if not symbol:
            continue
        quantity = _extract_float(
            raw,
            (
                "quantity_available_for_trading",
                "total_quantity",
                "quantity",
                "available_quantity",
                "balance",
            ),
        )
        if quantity <= 0:
            continue
        average_cost = _extract_float(raw, ("average_cost", "average_buy_price", "avg_cost", "cost_basis_price"))
        if average_cost <= 0:
            total_cost = _extract_float(raw, ("cost_basis", "total_cost"))
            average_cost = total_cost / quantity if total_cost > 0 else 0.0
        positions[symbol] = Position(symbol=symbol, quantity=quantity, average_cost=average_cost)
    return positions


def _crypto_asset_code(raw: dict[str, Any]) -> str:
    value = raw.get("asset_code") or raw.get("currency_code") or raw.get("code") or raw.get("symbol") or ""
    text = str(value).upper()
    if "-" in text:
        text = text.split("-", 1)[0]
    return text


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


def _review_is_approved(payload: dict[str, Any], alerts: tuple[str, ...]) -> bool:
    if not payload or payload.get("is_error"):
        return False
    if _has_blocking_alert(alerts, payload):
        return False
    state = str(payload.get("status") or payload.get("state") or "").lower()
    if state in {"rejected", "blocked", "error", "failed"}:
        return False
    return True


def _to_crypto_pair(symbol: str) -> str:
    normalized = symbol.upper()
    if "-" in normalized:
        return normalized
    return f"{normalized}-USD"


def _format_crypto_quantity(quantity: float) -> str:
    return f"{quantity:.8f}".rstrip("0").rstrip(".")
