"""Agentic bot orchestration."""

from __future__ import annotations

from pathlib import Path

from .config import AgenticConfig
from .journal import DecisionJournal, JournalEntry
from .market_data import Candle
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
        self.strategy = strategy or SimpleMomentumStrategy(target_dollars=min(10.0, config.risk.max_trade_dollars))
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

    def analyze_candles(
        self,
        symbol: str,
        candles: tuple[Candle, ...] | list[Candle],
        daily_trade_count: int = 0,
        strategy_name: str = "daily_trend_follow",
        has_position: bool = False,
        entry_price: float | None = None,
        peak_price: float | None = None,
    ) -> JournalEntry:
        if not candles:
            raise ValueError("analyze_candles requires at least one candle")

        strategy = self._strategies.get(strategy_name)
        if strategy is None:
            strategy = build_strategy(
                strategy_name,
                target_dollars=min(10.0, self.config.risk.max_trade_dollars),
            )
            self._strategies[strategy_name] = strategy

        if not hasattr(strategy, "evaluate_candles"):
            raise ValueError(f"strategy {strategy_name} does not support daily candles")

        decision = strategy.evaluate_candles(
            symbol,
            candles,
            has_position=has_position,
            entry_price=entry_price,
            peak_price=peak_price,
        )
        risk = self.risk.evaluate(decision, daily_trade_count=daily_trade_count)
        latest = candles[-1]
        previous_close = candles[-2].close if len(candles) > 1 else None
        quote = QuoteSnapshot(
            symbol=symbol.upper(),
            price=latest.close,
            previous_close=previous_close,
        )
        return self.journal.append(
            quote=quote,
            decision=decision,
            risk=risk,
            dry_run=self.config.dry_run,
        )
