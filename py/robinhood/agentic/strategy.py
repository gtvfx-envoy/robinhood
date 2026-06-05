"""Small deterministic strategies for agentic dry runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class QuoteSnapshot:
    """Minimal quote data needed by the first strategy."""

    symbol: str
    price: float
    previous_close: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Decision:
    """A strategy decision that can be risk checked and journaled."""

    symbol: str
    action: str
    confidence: float
    reason: str
    target_dollars: float = 0.0

    @property
    def is_trade(self) -> bool:
        return self.action in {"BUY", "SELL"}


class SimpleMomentumStrategy:
    """Buy/sell only when the current price moves enough from previous close."""

    def __init__(
        self,
        buy_threshold_pct: float = 1.0,
        sell_threshold_pct: float = -1.5,
        target_dollars: float = 10.0,
    ):
        self.buy_threshold_pct = buy_threshold_pct
        self.sell_threshold_pct = sell_threshold_pct
        self.target_dollars = target_dollars

    def evaluate(self, quote: QuoteSnapshot) -> Decision:
        if quote.previous_close is None or quote.previous_close <= 0:
            return Decision(
                symbol=quote.symbol,
                action="HOLD",
                confidence=0.0,
                reason="missing previous close",
            )

        move_pct = ((quote.price - quote.previous_close) / quote.previous_close) * 100.0
        confidence = min(abs(move_pct) / max(abs(self.buy_threshold_pct), 1.0), 1.0)

        if move_pct >= self.buy_threshold_pct:
            return Decision(
                symbol=quote.symbol,
                action="BUY",
                confidence=confidence,
                reason=f"price moved {move_pct:.2f}% above previous close",
                target_dollars=self.target_dollars,
            )

        if move_pct <= self.sell_threshold_pct:
            return Decision(
                symbol=quote.symbol,
                action="SELL",
                confidence=min(abs(move_pct) / max(abs(self.sell_threshold_pct), 1.0), 1.0),
                reason=f"price moved {move_pct:.2f}% below previous close",
                target_dollars=self.target_dollars,
            )

        return Decision(
            symbol=quote.symbol,
            action="HOLD",
            confidence=confidence,
            reason=f"price move {move_pct:.2f}% is inside thresholds",
        )
