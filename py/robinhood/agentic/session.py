"""Persistent paper-trading session runner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import time
from typing import Callable

from .bot import AgenticBot
from .broker import Broker, OrderIntent, OrderResult
from .config import AgenticConfig, LaneConfig
from .execution import plan_order_intent
from .journal import JournalEntry
from .market_data import Candle, CandleCollector, QuoteCollector
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


@dataclass(frozen=True)
class DailyPlanItem:
    symbol: str
    action: str
    confidence: float
    reason: str
    risk_approved: bool
    risk_reason: str
    broker_result: str


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
            self.bot.journal.append_execution(
                entry,
                {
                    "broker_status": "planned_rejected",
                    "broker_reason": plan.reason,
                    "order_intent": _intent_payload(plan.intent),
                    "placed": False,
                },
            )
            return f"no broker order: {plan.reason}"

        result = self.broker.place_order(plan.intent, price)
        self.bot.journal.append_execution(entry, _execution_payload(result))
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


class DailyCandleBrokerSession:
    """Evaluate daily-candle strategies and route approved intents to a broker."""

    def __init__(
        self,
        config: AgenticConfig,
        candle_collector: CandleCollector,
        broker: Broker,
        bot: AgenticBot | None = None,
        candle_range: str = "1y",
        order_result_reconciler: Callable[[OrderResult], OrderResult] | None = None,
    ):
        self.config = config
        self.candle_collector = candle_collector
        self.broker = broker
        self.bot = bot or AgenticBot(config)
        self.candle_range = candle_range
        self.order_result_reconciler = order_result_reconciler
        self._daily_trade_count = 0
        self._daily_trade_day = _current_trade_day()

    def run_once(self) -> SessionResult:
        decisions = 0
        skipped_quotes = 0
        collection_errors = 0
        lanes = self.config.lanes or (LaneConfig("stocks", self.config.symbols.stocks),)
        eligible_lanes = tuple(
            lane for lane in lanes if lane.strategy.strip().lower() in {"daily_trend_follow", "daily_trend"}
        )
        starting_snapshot = self.broker.get_account_snapshot()
        starting_positions = tuple(
            symbol
            for symbol, position in sorted(starting_snapshot.positions.items())
            if position.is_open
        )
        plan_items: list[DailyPlanItem] = []

        for lane in eligible_lanes:
            print(
                f"[daily] lane={lane.name} symbols={len(lane.symbols)} "
                f"strategy={lane.strategy} range={self.candle_range}"
            )
            candles_by_symbol, errors = self.candle_collector.collect(lane.symbols, range_=self.candle_range)
            collection_errors += len(errors)
            print(
                f"[daily] lane={lane.name} collected={len(candles_by_symbol)} "
                f"errors={len(errors)}"
            )
            for symbol, error in errors.items():
                print(f"{lane.name}/{symbol}: SKIP - {error}")

            snapshot = self.broker.get_account_snapshot()
            for symbol in lane.symbols:
                normalized = symbol.upper()
                candles = candles_by_symbol.get(normalized)
                if not candles:
                    if normalized not in errors:
                        skipped_quotes += 1
                        print(f"{lane.name}/{symbol}: SKIP - missing daily candles")
                    continue

                self._reset_daily_trade_count_if_needed()
                position = snapshot.positions.get(normalized)
                entry = self.bot.analyze_candles(
                    normalized,
                    candles,
                    daily_trade_count=self._daily_trade_count,
                    strategy_name=lane.strategy,
                    has_position=bool(position and position.is_open),
                    entry_price=position.average_cost if position else None,
                    peak_price=_peak_price(candles, position.average_cost if position else None),
                )
                decisions += 1
                result = self._apply_broker(entry, candles[-1].close)
                decision = entry.decision
                print(f"{lane.name}/{symbol}: {decision['action']} - {entry.risk['reason']} - {result}")
                plan_items.append(
                    DailyPlanItem(
                        symbol=normalized,
                        action=str(decision["action"]),
                        confidence=float(decision.get("confidence") or 0.0),
                        reason=str(decision.get("reason") or ""),
                        risk_approved=bool(entry.risk["approved"]),
                        risk_reason=str(entry.risk["reason"]),
                        broker_result=result,
                    )
                )
                snapshot = self.broker.get_account_snapshot()

        if plan_items:
            print(_daily_plan_summary_line(starting_positions, plan_items))

        snapshot = self.broker.get_account_snapshot()
        return SessionResult(
            iterations=1,
            decisions=decisions,
            skipped_quotes=skipped_quotes,
            collection_errors=collection_errors,
            paper_cash=snapshot.cash,
            positions={symbol: position.quantity for symbol, position in snapshot.positions.items()},
        )

    def _apply_broker(self, entry: JournalEntry, price: float) -> str:
        if not _is_approved_trade(entry):
            return "no broker review"

        decision = _decision_from_entry(entry)
        snapshot = self.broker.get_account_snapshot()
        plan = plan_order_intent(decision, snapshot, self.config.risk, price)
        if not plan.approved or plan.intent is None:
            self.bot.journal.append_execution(
                entry,
                {
                    "broker_status": "planned_rejected",
                    "broker_reason": plan.reason,
                    "order_intent": _intent_payload(plan.intent),
                    "placed": False,
                },
            )
            return f"no broker order: {plan.reason}"

        result = self.broker.place_order(plan.intent, price)
        if result.placed and self.order_result_reconciler is not None:
            result = self.order_result_reconciler(result)
        self.bot.journal.append_execution(entry, _execution_payload(result))
        if result.status in {"reviewed", "submitted", "filled"} or result.placed:
            self._daily_trade_count += 1
        return f"broker {result.status}: {result.reason}"

    def _reset_daily_trade_count_if_needed(self) -> None:
        trade_day = _current_trade_day()
        if trade_day != self._daily_trade_day:
            self._daily_trade_day = trade_day
            self._daily_trade_count = 0


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


def _execution_payload(result: OrderResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "broker_status": result.status,
        "broker_reason": result.reason,
        "placed": result.placed,
        "order_id": result.order_id,
        "filled_quantity": result.filled_quantity,
        "average_price": result.average_price,
        "order_intent": _intent_payload(result.intent),
    }
    review = _review_summary(result.raw)
    if review:
        payload["review"] = review
    return payload


def _intent_payload(intent: OrderIntent | None) -> dict[str, object] | None:
    if intent is None:
        return None
    return {
        "symbol": intent.symbol,
        "side": intent.side,
        "type": intent.order_type,
        "dollar_amount": intent.dollar_amount,
        "quantity": intent.quantity,
        "limit_price": intent.limit_price,
        "market_hours": intent.market_hours,
        "time_in_force": intent.time_in_force,
    }


def _review_summary(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        return {}

    summary: dict[str, object] = {}
    for key in (
        "status",
        "state",
        "estimated_quantity",
        "estimated_shares",
        "quantity",
        "estimated_cost",
        "notional",
        "last_trade_price",
        "estimated_price",
        "price",
    ):
        value = raw.get(key)
        if value is not None:
            summary[key] = value

    alerts = raw.get("alerts") or raw.get("pre_trade_alerts") or raw.get("warnings")
    if alerts:
        summary["alerts"] = alerts
    return summary


def _peak_price(candles: tuple[Candle, ...], entry_price: float | None) -> float | None:
    if entry_price is None:
        return None
    recent_high = max((candle.high for candle in candles), default=entry_price)
    return max(entry_price, recent_high)


def _daily_plan_summary_line(open_positions: tuple[str, ...], items: list[DailyPlanItem]) -> str:
    ranked_buys = tuple(
        sorted(
            (item for item in items if item.action == "BUY" and item.risk_approved),
            key=_daily_plan_buy_rank_key,
        )
    )
    buy_signals = tuple(item.symbol for item in ranked_buys)
    sell_signals = tuple(item.symbol for item in items if item.action == "SELL" and item.risk_approved)
    blocked = tuple(
        f"{item.symbol}:{_daily_plan_block_reason(item)}"
        for item in items
        if item.action in {"BUY", "SELL"} and _daily_plan_block_reason(item)
    )
    selected = tuple(
        f"{item.action}:{item.symbol}"
        for item in items
        if item.broker_result.startswith(("broker reviewed:", "broker submitted:", "broker filled:"))
    )
    selected_text = ",".join(selected) if selected else "HOLD"
    ranked_buy_text = _csv_or_dash(tuple(_daily_plan_buy_rank_text(item) for item in ranked_buys))
    top_buy_text = ranked_buys[0].symbol if ranked_buys else "-"
    return (
        "[daily-plan] "
        f"open_positions={_csv_or_dash(open_positions)} "
        f"buy_signals={_csv_or_dash(buy_signals)} "
        f"ranked_buys={ranked_buy_text} "
        f"top_buy={top_buy_text} "
        f"sell_signals={_csv_or_dash(sell_signals)} "
        f"blocked={_csv_or_dash(blocked)} "
        f"selected={selected_text}"
    )


def _daily_plan_block_reason(item: DailyPlanItem) -> str:
    if not item.risk_approved:
        return item.risk_reason
    prefix = "no broker order: "
    if item.broker_result.startswith(prefix):
        return item.broker_result[len(prefix):]
    return ""


def _daily_plan_buy_rank_key(item: DailyPlanItem) -> tuple[float, float, float, str]:
    trend = _extract_reason_pct(item.reason, "trend")
    atr = _extract_reason_pct(item.reason, "atr")
    trend_rank = trend if trend is not None else item.confidence
    atr_rank = atr if atr is not None else 9999.0
    return (-trend_rank, atr_rank, -item.confidence, item.symbol)


def _daily_plan_buy_rank_text(item: DailyPlanItem) -> str:
    trend = _extract_reason_pct(item.reason, "trend")
    atr = _extract_reason_pct(item.reason, "atr")
    if trend is not None and atr is not None:
        return f"{item.symbol}:trend={trend:.2f}/atr={atr:.2f}"
    if trend is not None:
        return f"{item.symbol}:trend={trend:.2f}"
    return f"{item.symbol}:confidence={item.confidence:.2f}"


def _extract_reason_pct(reason: str, key: str) -> float | None:
    match = re.search(rf"\b{re.escape(key)}=(-?\d+(?:\.\d+)?)%", reason)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _csv_or_dash(values: tuple[str, ...]) -> str:
    return ",".join(values) if values else "-"
