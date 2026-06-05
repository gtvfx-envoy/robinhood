"""Agentic bot orchestration."""

from __future__ import annotations

from pathlib import Path

from .config import AgenticConfig
from .journal import DecisionJournal, JournalEntry
from .risk import RiskManager
from .strategy import QuoteSnapshot, SimpleMomentumStrategy, build_strategy


class AgenticBot:
    """Run quote analysis, risk checks, and audit logging."""

    def __init__(
        self,
        config: AgenticConfig,
        strategy: SimpleMomentumStrategy | None = None,
        journal: DecisionJournal | None = None,
    ):
        self.config = config
        self.strategy = strategy or SimpleMomentumStrategy(
            target_dollars=min(10.0, config.risk.max_trade_dollars)
        )
        self._strategies = {"simple_momentum": self.strategy}
        self.risk = RiskManager(config)
        self.journal = journal or DecisionJournal(Path(config.journal_path))

    def analyze(
        self,
        quote: QuoteSnapshot,
        daily_trade_count: int = 0,
        strategy_name: str = "simple_momentum",
    ) -> JournalEntry:
        strategy = self._strategies.get(strategy_name)
        if strategy is None:
            strategy = build_strategy(
                strategy_name,
                target_dollars=min(10.0, self.config.risk.max_trade_dollars),
            )
            self._strategies[strategy_name] = strategy

        decision = strategy.evaluate(quote)
        risk = self.risk.evaluate(decision, daily_trade_count=daily_trade_count)
        return self.journal.append(
            quote=quote,
            decision=decision,
            risk=risk,
            dry_run=self.config.dry_run,
        )
