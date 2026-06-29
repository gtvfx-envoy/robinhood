"""Persistent market-aware daemon for daily-candle trading lanes."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .bot import AgenticBot
from .broker import AccountSnapshot, Broker, OrderIntent, OrderResult, OrderReview
from .config import AgenticConfig
from .daemon_state import DaemonState, DaemonStateStore, PendingOrderState
from .market_clock import MarketClock
from .market_data import CandleCollector, HistoricalMarketDataSource, YahooDailyCandleSource
from .session import DailyCandleBrokerSession, SessionResult


class PersistentDaemon:
    """Run daily-candle lanes according to market clock and persisted state."""

    def __init__(
        self,
        config: AgenticConfig,
        state_store: DaemonStateStore,
        broker_factory: Callable[[int], Broker],
        candle_file: Path | str,
        candle_range: str = "1y",
        clock: MarketClock | None = None,
        review_only: bool = False,
        max_live_order_dollars: float = 5.0,
        candle_source: HistoricalMarketDataSource | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        now_fn: Callable[[], datetime] | None = None,
        order_result_reconciler: Callable[[OrderResult], OrderResult] | None = None,
    ):
        self.config = config
        self.state_store = state_store
        self.broker_factory = broker_factory
        self.candle_file = Path(candle_file)
        self.candle_range = candle_range
        self.clock = clock or MarketClock(pre_open_warmup_minutes=config.pre_open_warmup_minutes)
        self.review_only = review_only
        self.max_live_order_dollars = max_live_order_dollars
        self.candle_source = candle_source or YahooDailyCandleSource()
        self.sleep_fn = sleep_fn
        self.now_fn = now_fn
        self.order_result_reconciler = order_result_reconciler

    def run(self, max_iterations: int | None = None, status_only: bool = False) -> SessionResult:
        iterations = 0
        decisions = 0
        skipped = 0
        errors = 0
        last_result = SessionResult(0, 0, 0, 0, 0.0, {})

        while max_iterations is None or iterations < max_iterations:
            iterations += 1
            status = self.clock.status(self.now_fn() if self.now_fn else None)
            state = self.state_store.load().for_trade_day(status.trade_day)
            self.state_store.save(state)
            self._print_status(status, state)

            if status_only:
                break
            if status.warmup_allowed:
                state = replace(state, last_warmup_at=status.now.isoformat())
                self._collect_daily_candles()
                self.state_store.save(state)
                print("[daemon] warmup collected daily candles")
            elif status.trading_allowed:
                if _daily_lane_due(self.config, state, status.trade_day):
                    result = self._run_daily_lanes(state, status.trade_day or "")
                    last_result = result
                    decisions += result.decisions
                    skipped += result.skipped_quotes
                    errors += result.collection_errors
                else:
                    print("[daemon] daily lanes already evaluated for this trading day")

            if max_iterations is not None and iterations >= max_iterations:
                break
            self.sleep_fn(self._sleep_seconds(status))

        return replace(
            last_result,
            iterations=iterations,
            decisions=decisions,
            skipped_quotes=skipped,
            collection_errors=errors,
        )

    def _run_daily_lanes(self, state: DaemonState, trade_day: str) -> SessionResult:
        remaining_attempts = max(0, self.config.risk.max_live_order_attempts_per_day - state.live_order_attempts)
        broker = self.broker_factory(max(1, remaining_attempts))
        broker = StateBackedBroker(
            broker,
            self.state_store,
            self.config,
            live_limits_enabled=not self.review_only,
        )
        effective_config = _daemon_effective_config(self.config, self.max_live_order_dollars)
        bot = AgenticBot(config=effective_config)
        session = DailyCandleBrokerSession(
            config=effective_config,
            candle_collector=CandleCollector(self.candle_source, self.candle_file),
            broker=broker,
            bot=bot,
            candle_range=self.candle_range,
            order_result_reconciler=self.order_result_reconciler,
        )
        result = session.run_once()
        state = self.state_store.load().for_trade_day(trade_day)
        lane_evaluations = dict(state.lane_evaluations)
        for lane in _daily_lanes(self.config):
            lane_evaluations[lane.name] = trade_day
        self.state_store.save(replace(state, lane_evaluations=lane_evaluations))
        print(
            "[daemon-summary] "
            f"trade_day={trade_day} decisions={result.decisions} "
            f"skipped_candles={result.skipped_quotes} collection_errors={result.collection_errors} "
            f"account_cash=${result.paper_cash:.2f}"
        )
        return result

    def _collect_daily_candles(self) -> None:
        symbols = []
        for lane in _daily_lanes(self.config):
            symbols.extend(lane.symbols)
        if symbols:
            CandleCollector(self.candle_source, self.candle_file).collect(symbols, range_=self.candle_range)

    def _sleep_seconds(self, status) -> float:
        if status.state in {"closed", "after_close", "warmup"}:
            return min(self.config.poll_seconds, self.clock.seconds_until(status.next_wakeup, status.now))
        return self.config.poll_seconds

    def _print_status(self, status, state: DaemonState) -> None:
        print(
            "[daemon] "
            f"state={status.state} trade_day={status.trade_day or '-'} "
            f"attempts={state.live_order_attempts}/{self.config.risk.max_live_order_attempts_per_day} "
            f"next_wakeup={status.next_wakeup.isoformat()}"
        )


class StateBackedBroker(Broker):
    """Broker wrapper that enforces persisted daily live-order limits."""

    def __init__(
        self,
        broker: Broker,
        state_store: DaemonStateStore,
        config: AgenticConfig,
        live_limits_enabled: bool = True,
    ):
        self.broker = broker
        self.state_store = state_store
        self.config = config
        self.live_limits_enabled = live_limits_enabled

    def get_account_snapshot(self) -> AccountSnapshot:
        return self.broker.get_account_snapshot()

    def review_order(self, intent: OrderIntent, price: float) -> OrderReview:
        return self.broker.review_order(intent, price)

    def place_order(self, intent: OrderIntent, price: float) -> OrderResult:
        if not self.live_limits_enabled:
            return self.broker.place_order(intent, price)

        state = self.state_store.load()
        dollars = _intent_dollars(intent, price)
        blocked = self._block_reason(state, dollars)
        if blocked:
            return OrderResult(intent=intent, placed=False, status="rejected", reason=blocked)

        state = replace(
            state,
            live_order_attempts=state.live_order_attempts + 1,
            live_notional_attempted=state.live_notional_attempted + dollars,
        )
        self.state_store.save(state)

        result = self.broker.place_order(intent, price)
        state = self.state_store.load()
        pending = list(state.pending_orders)
        live_orders_submitted = state.live_orders_submitted
        live_notional_submitted = state.live_notional_submitted
        if result.placed:
            live_orders_submitted += 1
            live_notional_submitted += dollars
        if result.placed or result.status == "unconfirmed":
            pending.append(
                PendingOrderState(
                    ref_id=intent.ref_id,
                    symbol=intent.symbol,
                    side=intent.side,
                    status=result.status,
                    order_id=result.order_id,
                    dollar_amount=dollars,
                    timestamp=result.timestamp,
                )
            )
        self.state_store.save(
            replace(
                state,
                live_orders_submitted=live_orders_submitted,
                live_notional_submitted=live_notional_submitted,
                pending_orders=tuple(pending),
            )
        )
        return result

    def _block_reason(self, state: DaemonState, dollars: float) -> str:
        if state.pending_orders:
            return "pending or unconfirmed order requires reconciliation"
        if state.live_order_attempts >= self.config.risk.max_live_order_attempts_per_day:
            return "daily live order attempt limit reached"
        max_notional = self.config.risk.max_live_notional_per_day or self.config.risk.max_trade_dollars
        if max_notional > 0 and state.live_notional_attempted + dollars > max_notional:
            return "daily live notional limit reached"
        return ""


def _daemon_effective_config(config: AgenticConfig, max_live_order_dollars: float) -> AgenticConfig:
    risk = replace(config.risk, max_trade_dollars=min(config.risk.max_trade_dollars, max_live_order_dollars))
    return replace(config, risk=risk)


def _daily_lanes(config: AgenticConfig):
    return tuple(
        lane for lane in config.lanes if lane.strategy.strip().lower() in {"daily_trend_follow", "daily_trend"}
    )


def _daily_lane_due(config: AgenticConfig, state: DaemonState, trade_day: str | None) -> bool:
    if not trade_day:
        return False
    return any(state.lane_evaluations.get(lane.name) != trade_day for lane in _daily_lanes(config))


def _intent_dollars(intent: OrderIntent, price: float) -> float:
    if intent.dollar_amount is not None:
        return float(intent.dollar_amount)
    return float(intent.quantity or 0.0) * price
