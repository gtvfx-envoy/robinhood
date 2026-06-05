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

        if decision.symbol not in self.config.symbols.stocks:
            return RiskResult(False, f"{decision.symbol} is not in allowed stock symbols")

        if decision.action == "SELL" and not self.config.risk.allow_shorts:
            return RiskResult(False, "sell decisions require position-aware checks")

        if decision.target_dollars <= 0:
            return RiskResult(False, "target dollars must be positive")

        if decision.target_dollars > self.config.risk.max_trade_dollars:
            return RiskResult(False, "target dollars exceeds max trade size")

        if daily_trade_count >= self.config.risk.max_daily_trades:
            return RiskResult(False, "daily trade limit reached")

        return RiskResult(True, "approved for dry-run review")
