"""Risk checks for proposed agentic decisions."""

from __future__ import annotations

from dataclasses import dataclass

from .config import AgenticConfig
from .strategy import Decision


@dataclass(frozen=True)
class RiskResult:
    approved: bool
    reason: str


class RiskManager:
    """Evaluate decisions against hard-coded account safety constraints."""

    def __init__(self, config: AgenticConfig):
        self.config = config

    def evaluate(self, decision: Decision, daily_trade_count: int = 0) -> RiskResult:
        if not decision.is_trade:
            return RiskResult(True, "no trade requested")

        allowed_symbols = set(self.config.symbols.stocks) | set(self.config.symbols.crypto)
        if decision.symbol not in allowed_symbols:
            return RiskResult(False, f"{decision.symbol} is not in allowed symbols")

        if daily_trade_count >= self.config.risk.max_daily_trades:
            return RiskResult(False, "daily trade limit reached")

        if decision.action == "SELL":
            return RiskResult(True, "approved for paper sell review")

        if decision.target_dollars <= 0:
            return RiskResult(False, "target dollars must be positive")

        if decision.target_dollars < self.config.risk.min_order_dollars:
            return RiskResult(False, "target dollars below minimum order size")

        if decision.target_dollars > self.config.risk.max_trade_dollars:
            return RiskResult(False, "target dollars exceeds max trade size")

        return RiskResult(True, "approved for dry-run review")
