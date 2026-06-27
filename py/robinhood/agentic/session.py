"""Persistent paper-trading session runner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time

from .bot import AgenticBot
from .broker import Broker
from .config import AgenticConfig, LaneConfig
from .execution import plan_order_intent
from .journal import JournalEntry
from .market_data import QuoteCollector
from .paper import PaperAccount
from .quotes import QuoteProvider, QuoteUnavailable
from .strategy import Decision


@dataclass(frozen=True)
class SessionResult:
    iterations: int
    decisions: int
    skipped_quotes: int
    collection_errors: int
    paper_cash: float
    positions: dict[str, float]
    interrupted: bool = False


class PaperSession:
    """Poll quote data, analyze configured symbols, and simulate fills."""

    def __init__(
        self,
        config: AgenticConfig,
        quote_provider: QuoteProvider,
        quote_collector: QuoteCollector | None = None,
        bot: AgenticBot | None = None,
        paper_account: PaperAccount | None = None,
        show_progress: bool = True,
    ):
        self.config = config
        self.quote_provider = quote_provider
        self.quote_collector = quote_collector
        self.bot = bot or AgenticBot(config)
        self.paper_account = paper_account or PaperAccount(config.paper_starting_cash)
        self.show_progress = show_progress
        self._lane_next_run: dict[str, float] = {}
        self._daily_trade_count = 0
        self._daily_trade_day = _current_trade_day()

    def run(self, max_iterations: int | None = None) -> SessionResult:
        iterations = 0
        decisions = 0
        skipped_quotes = 0
        collection_errors = 0
        interrupted = False

        try:
            while max_iterations is None or iterations < max_iterations:
                iterations += 1
                for lane in self._due_lanes():
                    print(
                        f"[poll] lane={lane.name} symbols={len(lane.symbols)} "
                        f"strategy={lane.strategy} interval={lane.poll_seconds:.0f}s"
                    )
                    quotes, errors = self._collect_lane_quotes(lane)
                    collection_errors += len(errors)
                    print(
                        f"[poll] lane={lane.name} collected={len(quotes)} "
                        f"errors={len(errors)}"
                    )
                    for symbol, error in errors.items():
                        print(f"{lane.name}/{symbol}: SKIP - {error}")

                    for symbol in lane.symbols:
                        normalized = symbol.upper()
                        quote = quotes.get(normalized)
                        if quote is None:
                            try:
                                quote = self.quote_provider.get_quote(symbol)
                            except QuoteUnavailable as exc:
                                if normalized not in errors:
                                    skipped_quotes += 1
                                    print(f"{lane.name}/{symbol}: SKIP - {exc}")
                                continue

                        self._reset_daily_trade_count_if_needed()
                        entry = self.bot.analyze(
                            quote,
                            daily_trade_count=self._daily_trade_count,
                            strategy_name=lane.strategy,
                        )
                        decisions += 1
                        fill = self.paper_account.apply(entry, quote)
                        if _is_approved_trade(entry):
                            self._daily_trade_count += 1
                        decision = entry.decision
                        print(f"{lane.name}/{symbol}: {decision['action']} - {entry.risk['reason']} - {fill}")

                    self._mark_lane_complete(lane)

                if max_iterations is not None and iterations >= max_iterations:
                    break
                self._sleep_until_next_poll()
        except KeyboardInterrupt:
            interrupted = True
            print("\n[stop] keyboard interrupt received; stopping paper session")

        return SessionResult(
            iterations=iterations,
            decisions=decisions,
            skipped_quotes=skipped_quotes,
            collection_errors=collection_errors,
            paper_cash=self.paper_account.cash,
            positions=dict(self.paper_account.positions),
            interrupted=interrupted,
        )

    def _due_lanes(self) -> tuple[LaneConfig, ...]:
        now = time.monotonic()
        lanes = self.config.lanes or (LaneConfig("stocks", self.config.symbols.stocks),)
        return tuple(lane for lane in lanes if now >= self._lane_next_run.get(lane.name, 0.0))

    def _collect_lane_quotes(self, lane: LaneConfig):
        if self.quote_collector is None:
            return {}, {}
        return self.quote_collector.collect(lane.symbols)

    def _mark_lane_complete(self, lane: LaneConfig) -> None:
        self._lane_next_run[lane.name] = time.monotonic() + lane.poll_seconds

    def _reset_daily_trade_count_if_needed(self) -> None:
        trade_day = _current_trade_day()
        if trade_day != self._daily_trade_day:
            self._daily_trade_day = trade_day
            self._daily_trade_count = 0

    def _sleep_seconds(self) -> float:
        if not self._lane_next_run:
            return self.config.poll_seconds

        next_due = min(self._lane_next_run.values())
        return max(0.1, min(self.config.poll_seconds, next_due - time.monotonic()))

    def _next_due_lane_names(self) -> tuple[str, ...]:
        if not self._lane_next_run:
            return ()

        next_due = min(self._lane_next_run.values())
        return tuple(
            name for name, due_at in self._lane_next_run.items()
            if abs(due_at - next_due) < 0.001
        )

    def _sleep_until_next_poll(self) -> None:
        seconds = self._sleep_seconds()
        lanes = ", ".join(self._next_due_lane_names()) or "unknown"
        if not self.show_progress:
            time.sleep(seconds)
            return

        _sleep_with_progress(seconds, f"next poll: {lanes}")


class BrokerSession:
    """Poll quote data, analyze configured symbols, and route intents to a broker."""

    def __init__(
        self,
        config: AgenticConfig,
        quote_provider: QuoteProvider,
        broker: Broker,
        quote_collector: QuoteCollector | None = None,
        bot: AgenticBot | None = None,
        show_progress: bool = True,
    ):
        self.config = config
        self.quote_provider = quote_provider
        self.broker = broker
        self.quote_collector = quote_collector
        self.bot = bot or AgenticBot(config)
        self.show_progress = show_progress
        self._lane_next_run: dict[str, float] = {}
        self._daily_trade_count = 0
        self._daily_trade_day = _current_trade_day()

    def run(self, max_iterations: int | None = None) -> SessionResult:
        iterations = 0
        decisions = 0
        skipped_quotes = 0
        collection_errors = 0
        interrupted = False

        try:
            while max_iterations is None or iterations < max_iterations:
                iterations += 1
                for lane in self._due_lanes():
                    print(
                        f"[poll] lane={lane.name} symbols={len(lane.symbols)} "
                        f"strategy={lane.strategy} interval={lane.poll_seconds:.0f}s"
                    )
                    quotes, errors = self._collect_lane_quotes(lane)
                    collection_errors += len(errors)
                    print(
                        f"[poll] lane={lane.name} collected={len(quotes)} "
                        f"errors={len(errors)}"
                    )
                    for symbol, error in errors.items():
                        print(f"{lane.name}/{symbol}: SKIP - {error}")

                    for symbol in lane.symbols:
                        normalized = symbol.upper()
                        quote = quotes.get(normalized)
                        if quote is None:
                            try:
                                quote = self.quote_provider.get_quote(symbol)
                            except QuoteUnavailable as exc:
                                if normalized not in errors:
                                    skipped_quotes += 1
                                    print(f"{lane.name}/{symbol}: SKIP - {exc}")
                                continue

                        self._reset_daily_trade_count_if_needed()
                        entry = self.bot.analyze(
                            quote,
                            daily_trade_count=self._daily_trade_count,
                            strategy_name=lane.strategy,
                        )
                        decisions += 1
                        result = self._apply_broker(entry, quote.price)
                        decision = entry.decision
                        print(f"{lane.name}/{symbol}: {decision['action']} - {entry.risk['reason']} - {result}")

                    self._mark_lane_complete(lane)

                if max_iterations is not None and iterations >= max_iterations:
                    break
                self._sleep_until_next_poll()
        except KeyboardInterrupt:
            interrupted = True
            print("\n[stop] keyboard interrupt received; stopping broker session")

        snapshot = self.broker.get_account_snapshot()
        return SessionResult(
            iterations=iterations,
            decisions=decisions,
            skipped_quotes=skipped_quotes,
            collection_errors=collection_errors,
            paper_cash=snapshot.cash,
            positions={symbol: position.quantity for symbol, position in snapshot.positions.items()},
            interrupted=interrupted,
        )

    def _apply_broker(self, entry: JournalEntry, price: float) -> str:
        if not _is_approved_trade(entry):
            return "no broker review"

        decision = _decision_from_entry(entry)
        snapshot = self.broker.get_account_snapshot()
        plan = plan_order_intent(decision, snapshot, self.config.risk, price)
        if not plan.approved or plan.intent is None:
            return f"no broker order: {plan.reason}"

        result = self.broker.place_order(plan.intent, price)
        if result.status in {"reviewed", "submitted", "filled"} or result.placed:
            self._daily_trade_count += 1
        return f"broker {result.status}: {result.reason}"

    def _due_lanes(self) -> tuple[LaneConfig, ...]:
        now = time.monotonic()
        lanes = self.config.lanes or (LaneConfig("stocks", self.config.symbols.stocks),)
        return tuple(lane for lane in lanes if now >= self._lane_next_run.get(lane.name, 0.0))

    def _collect_lane_quotes(self, lane: LaneConfig):
        if self.quote_collector is None:
            return {}, {}
        return self.quote_collector.collect(lane.symbols)

    def _mark_lane_complete(self, lane: LaneConfig) -> None:
        self._lane_next_run[lane.name] = time.monotonic() + lane.poll_seconds

    def _reset_daily_trade_count_if_needed(self) -> None:
        trade_day = _current_trade_day()
        if trade_day != self._daily_trade_day:
            self._daily_trade_day = trade_day
            self._daily_trade_count = 0

    def _sleep_seconds(self) -> float:
        if not self._lane_next_run:
            return self.config.poll_seconds

        next_due = min(self._lane_next_run.values())
        return max(0.1, min(self.config.poll_seconds, next_due - time.monotonic()))

    def _next_due_lane_names(self) -> tuple[str, ...]:
        if not self._lane_next_run:
            return ()

        next_due = min(self._lane_next_run.values())
        return tuple(
            name for name, due_at in self._lane_next_run.items()
            if abs(due_at - next_due) < 0.001
        )

    def _sleep_until_next_poll(self) -> None:
        seconds = self._sleep_seconds()
        lanes = ", ".join(self._next_due_lane_names()) or "unknown"
        if not self.show_progress:
            time.sleep(seconds)
            return

        _sleep_with_progress(seconds, f"next poll: {lanes}")


def _sleep_with_progress(seconds: float, label: str, width: int = 24) -> None:
    if seconds <= 0:
        return

    started = time.monotonic()
    deadline = started + seconds
    while True:
        now = time.monotonic()
        remaining = max(0.0, deadline - now)
        elapsed = min(seconds, seconds - remaining)
        ratio = 1.0 if seconds <= 0 else elapsed / seconds
        filled = min(width, int(width * ratio))
        bar = "#" * filled + "-" * (width - filled)
        print(f"\r[{bar}] {label} in {remaining:5.1f}s", end="", flush=True)

        if remaining <= 0:
            print()
            return
        time.sleep(min(1.0, remaining))


def _current_trade_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _is_approved_trade(entry: JournalEntry) -> bool:
    return bool(entry.risk["approved"]) and entry.decision["action"] in {"BUY", "SELL"}


def _decision_from_entry(entry: JournalEntry) -> Decision:
    decision = entry.decision
    return Decision(
        symbol=str(decision["symbol"]),
        action=str(decision["action"]),
        confidence=float(decision.get("confidence") or 0.0),
        reason=str(decision.get("reason") or ""),
        target_dollars=float(decision.get("target_dollars") or 0.0),
    )
