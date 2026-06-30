"""Persistent daemon state used for restart-safe trading limits."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


@dataclass(frozen=True)
class PendingOrderState:
    ref_id: str
    symbol: str
    side: str
    status: str
    order_id: str = ""
    dollar_amount: float = 0.0
    timestamp: str = ""


@dataclass(frozen=True)
class DaemonState:
    trading_day: str = ""
    last_warmup_at: str = ""
    last_reconciliation_at: str = ""
    lane_evaluations: dict[str, str] = field(default_factory=dict)
    live_order_attempts: int = 0
    live_orders_submitted: int = 0
    live_notional_attempted: float = 0.0
    live_notional_submitted: float = 0.0
    pending_orders: tuple[PendingOrderState, ...] = ()

    def for_trade_day(self, trade_day: str | None) -> DaemonState:
        if not trade_day or self.trading_day == trade_day:
            return self
        return DaemonState(trading_day=trade_day)


class DaemonStateStore:
    """Load and atomically save daemon state JSON."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load(self) -> DaemonState:
        if not self.path.exists():
            return DaemonState()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid daemon state JSON: {self.path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("daemon state root must be an object")
        return _state_from_payload(payload)

    def save(self, state: DaemonState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(state)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            tmp_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        tmp_path.replace(self.path)


def daemon_state_summary(state: DaemonState, path: Path | str | None = None) -> str:
    path_text = f" path={path}" if path else ""
    lines = [
        f"[daemon-state]{path_text}",
        f"trading_day={state.trading_day or '-'}",
        f"last_warmup_at={state.last_warmup_at or '-'}",
        f"last_reconciliation_at={state.last_reconciliation_at or '-'}",
        f"live_order_attempts={state.live_order_attempts}",
        f"live_orders_submitted={state.live_orders_submitted}",
        f"live_notional_attempted=${state.live_notional_attempted:.2f}",
        f"live_notional_submitted=${state.live_notional_submitted:.2f}",
        f"lane_evaluations={state.lane_evaluations or {}}",
        f"pending_orders={len(state.pending_orders)}",
    ]
    for index, order in enumerate(state.pending_orders, start=1):
        lines.append(
            "pending_order "
            f"{index}: symbol={order.symbol} side={order.side} status={order.status} "
            f"dollars=${order.dollar_amount:.2f} order_id={order.order_id or '-'} "
            f"ref_id={order.ref_id or '-'} timestamp={order.timestamp or '-'}"
        )
    return "\n".join(lines)


def replace_state_pending(state: DaemonState, pending_orders: tuple[PendingOrderState, ...]) -> DaemonState:
    return DaemonState(
        trading_day=state.trading_day,
        last_warmup_at=state.last_warmup_at,
        last_reconciliation_at=datetime.now(UTC).isoformat(),
        lane_evaluations=dict(state.lane_evaluations),
        live_order_attempts=state.live_order_attempts,
        live_orders_submitted=state.live_orders_submitted,
        live_notional_attempted=state.live_notional_attempted,
        live_notional_submitted=state.live_notional_submitted,
        pending_orders=tuple(pending_orders),
    )


def clear_pending_orders(state: DaemonState) -> DaemonState:
    return replace_state_pending(state, ())


def reset_trade_day_after_unresolved_order(state: DaemonState) -> DaemonState:
    return DaemonState(
        trading_day=state.trading_day,
        last_warmup_at=state.last_warmup_at,
        last_reconciliation_at=datetime.now(UTC).isoformat(),
        lane_evaluations={},
        live_order_attempts=0,
        live_orders_submitted=0,
        live_notional_attempted=0.0,
        live_notional_submitted=0.0,
        pending_orders=(),
    )


def _state_from_payload(payload: dict[str, Any]) -> DaemonState:
    pending = payload.get("pending_orders") or []
    if not isinstance(pending, list):
        pending = []
    pending_orders = tuple(_pending_order_from_payload(item) for item in pending if isinstance(item, dict))
    return DaemonState(
        trading_day=str(payload.get("trading_day") or ""),
        last_warmup_at=str(payload.get("last_warmup_at") or ""),
        last_reconciliation_at=str(payload.get("last_reconciliation_at") or ""),
        lane_evaluations={str(key): str(value) for key, value in (payload.get("lane_evaluations") or {}).items()}
        if isinstance(payload.get("lane_evaluations"), dict)
        else {},
        live_order_attempts=int(payload.get("live_order_attempts") or 0),
        live_orders_submitted=int(payload.get("live_orders_submitted") or 0),
        live_notional_attempted=float(payload.get("live_notional_attempted") or 0.0),
        live_notional_submitted=float(payload.get("live_notional_submitted") or 0.0),
        pending_orders=pending_orders,
    )


def _pending_order_from_payload(payload: dict[str, Any]) -> PendingOrderState:
    return PendingOrderState(
        ref_id=str(payload.get("ref_id") or ""),
        symbol=str(payload.get("symbol") or "").upper(),
        side=str(payload.get("side") or ""),
        status=str(payload.get("status") or ""),
        order_id=str(payload.get("order_id") or ""),
        dollar_amount=float(payload.get("dollar_amount") or 0.0),
        timestamp=str(payload.get("timestamp") or ""),
    )
