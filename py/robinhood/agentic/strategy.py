"""Small deterministic strategies for agentic dry runs."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .indicators import atr, ema, percent_change


@dataclass(frozen=True)
class QuoteSnapshot:
    """Minimal quote data needed by the first strategy."""

    symbol: str
    price: float
    previous_close: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


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


@dataclass(frozen=True)
class CryptoTrendSnapshot:
    """Deterministic crypto scalp inputs used to explain every decision."""

    fast_ema: float
    slow_ema: float
    rsi: float
    tick_move_pct: float
    edge_pct: float


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


class HoldStrategy:
    """Always hold; useful for lanes that are configured before strategy support exists."""

    def evaluate(self, quote: QuoteSnapshot) -> Decision:
        return Decision(
            symbol=quote.symbol,
            action="HOLD",
            confidence=0.0,
            reason="lane strategy is hold",
        )


class DailyTrendFollowStrategy:
    """Long-only daily trend following for small cash accounts."""

    def __init__(
        self,
        target_dollars: float = 10.0,
        short_period: int = 20,
        long_period: int = 50,
        atr_period: int = 14,
        min_trend_pct: float = 0.05,
        max_daily_move_pct: float = 7.5,
        stop_loss_pct: float = -6.0,
        trailing_stop_pct: float = 8.0,
    ):
        self.target_dollars = target_dollars
        self.short_period = short_period
        self.long_period = long_period
        self.atr_period = atr_period
        self.min_trend_pct = min_trend_pct
        self.max_daily_move_pct = max_daily_move_pct
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self._closes = defaultdict(lambda: deque(maxlen=max(long_period, atr_period) + 2))
        self._highs = defaultdict(lambda: deque(maxlen=max(long_period, atr_period) + 2))
        self._lows = defaultdict(lambda: deque(maxlen=max(long_period, atr_period) + 2))
        self.entry_price: dict[str, float] = {}
        self.peak_price: dict[str, float] = {}

    def evaluate(self, quote: QuoteSnapshot) -> Decision:
        symbol = quote.symbol.upper()
        self._closes[symbol].append(quote.price)
        self._highs[symbol].append(quote.price)
        self._lows[symbol].append(quote.price)
        return self._evaluate_series(
            symbol=symbol,
            closes=list(self._closes[symbol]),
            highs=list(self._highs[symbol]),
            lows=list(self._lows[symbol]),
            has_position=symbol in self.entry_price,
            entry_price=self.entry_price.get(symbol),
            peak_price=self.peak_price.get(symbol),
        )

    def evaluate_candles(
        self,
        symbol: str,
        candles: tuple[Any, ...] | list[Any],
        has_position: bool = False,
        entry_price: float | None = None,
        peak_price: float | None = None,
    ) -> Decision:
        normalized = symbol.upper()
        closes = [float(candle.close) for candle in candles]
        highs = [float(candle.high) for candle in candles]
        lows = [float(candle.low) for candle in candles]
        return self._evaluate_series(
            symbol=normalized,
            closes=closes,
            highs=highs,
            lows=lows,
            has_position=has_position,
            entry_price=entry_price,
            peak_price=peak_price,
        )

    def _evaluate_series(
        self,
        symbol: str,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        has_position: bool,
        entry_price: float | None,
        peak_price: float | None,
    ) -> Decision:
        required = max(self.long_period, self.atr_period) + 1
        if len(closes) < required:
            return Decision(
                symbol=symbol,
                action="HOLD",
                confidence=0.0,
                reason=f"warming up daily trend history {len(closes)}/{required}",
            )

        close = closes[-1]
        previous_close = closes[-2]
        short_ema = ema(closes[-self.short_period :], self.short_period)
        long_ema = ema(closes[-self.long_period :], self.long_period)
        trend_pct = percent_change(short_ema, long_ema)
        day_move_pct = percent_change(close, previous_close)
        atr_value = atr(highs, lows, closes, self.atr_period)
        atr_pct = percent_change(close + atr_value, close)

        if has_position:
            return self._evaluate_exit(
                symbol=symbol,
                close=close,
                long_ema=long_ema,
                entry_price=entry_price or close,
                peak_price=peak_price or close,
            )

        if abs(day_move_pct) > self.max_daily_move_pct:
            return Decision(
                symbol=symbol,
                action="HOLD",
                confidence=0.0,
                reason=f"daily move {day_move_pct:.2f}% exceeds spike filter",
            )

        if close > long_ema and short_ema > long_ema and trend_pct >= self.min_trend_pct:
            confidence = min(max(trend_pct / max(self.min_trend_pct * 4, 0.01), 0.0), 1.0)
            self.entry_price[symbol] = close
            self.peak_price[symbol] = close
            return Decision(
                symbol=symbol,
                action="BUY",
                confidence=confidence,
                reason=(
                    f"daily trend entry close={close:.2f} "
                    f"ema{self.short_period}={short_ema:.2f} "
                    f"ema{self.long_period}={long_ema:.2f} "
                    f"trend={trend_pct:.2f}% atr={atr_pct:.2f}%"
                ),
                target_dollars=self.target_dollars,
            )

        return Decision(
            symbol=symbol,
            action="HOLD",
            confidence=0.0,
            reason=(
                f"no daily trend entry close={close:.2f} "
                f"ema{self.short_period}={short_ema:.2f} "
                f"ema{self.long_period}={long_ema:.2f} trend={trend_pct:.2f}%"
            ),
        )

    def _evaluate_exit(
        self,
        symbol: str,
        close: float,
        long_ema: float,
        entry_price: float,
        peak_price: float,
    ) -> Decision:
        peak = max(peak_price, close)
        self.peak_price[symbol] = peak
        pnl_pct = percent_change(close, entry_price)
        drawdown_pct = percent_change(close, peak)

        if close < long_ema:
            self.entry_price.pop(symbol, None)
            self.peak_price.pop(symbol, None)
            return Decision(
                symbol=symbol,
                action="SELL",
                confidence=1.0,
                reason=f"daily trend exit close={close:.2f} below ema{self.long_period}={long_ema:.2f}",
            )

        if pnl_pct <= self.stop_loss_pct:
            self.entry_price.pop(symbol, None)
            self.peak_price.pop(symbol, None)
            return Decision(
                symbol=symbol,
                action="SELL",
                confidence=1.0,
                reason=f"daily trend stop loss pnl={pnl_pct:.2f}%",
            )

        if drawdown_pct <= -self.trailing_stop_pct:
            self.entry_price.pop(symbol, None)
            self.peak_price.pop(symbol, None)
            return Decision(
                symbol=symbol,
                action="SELL",
                confidence=1.0,
                reason=f"daily trend trailing stop drawdown={drawdown_pct:.2f}%",
            )

        return Decision(
            symbol=symbol,
            action="HOLD",
            confidence=0.0,
            reason=f"holding daily trend pnl={pnl_pct:.2f}% drawdown={drawdown_pct:.2f}%",
        )


class CryptoScalpStrategy:
    """Stateful crypto scalping strategy for paper trading.

    This strategy needs several polling ticks before it can act. It buys only
    when short-term momentum has enough estimated edge to clear friction, then
    exits on take-profit, stop-loss, or trailing stop.
    """

    def __init__(
        self,
        target_dollars: float = 10.0,
        fast_period: int = 3,
        slow_period: int = 8,
        rsi_period: int = 7,
        min_edge_pct: float = 0.18,
        take_profit_pct: float = 0.45,
        stop_loss_pct: float = -0.35,
        trailing_stop_pct: float = 0.25,
        buy_rsi_min: float = 45.0,
        buy_rsi_max: float = 72.0,
    ):
        self.target_dollars = target_dollars
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.rsi_period = rsi_period
        self.min_edge_pct = min_edge_pct
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.buy_rsi_min = buy_rsi_min
        self.buy_rsi_max = buy_rsi_max
        self.history = defaultdict(lambda: deque(maxlen=max(slow_period, rsi_period) + 2))
        self.entry_price: dict[str, float] = {}
        self.peak_price: dict[str, float] = {}

    def evaluate(
        self,
        quote: QuoteSnapshot,
        has_position: bool | None = None,
        entry_price: float | None = None,
        peak_price: float | None = None,
    ) -> Decision:
        symbol = quote.symbol.upper()
        if quote.price <= 0:
            return Decision(
                symbol=symbol,
                action="HOLD",
                confidence=0.0,
                reason="crypto scalp price must be positive",
            )

        prices = self.history[symbol]
        prices.append(quote.price)

        position_open = symbol in self.entry_price if has_position is None else has_position
        if position_open:
            resolved_entry = _first_positive(entry_price, self.entry_price.get(symbol), quote.price)
            resolved_peak = _first_positive(peak_price, self.peak_price.get(symbol), resolved_entry, quote.price)
            if prices:
                resolved_peak = max(resolved_peak, max(prices))
            self.entry_price[symbol] = resolved_entry
            self.peak_price[symbol] = resolved_peak
            return self._evaluate_exit(symbol, quote.price, resolved_entry, resolved_peak)

        if has_position is False:
            self.entry_price.pop(symbol, None)
            self.peak_price.pop(symbol, None)

        required = max(self.slow_period, self.rsi_period) + 1
        if len(prices) < required:
            return Decision(
                symbol=symbol,
                action="HOLD",
                confidence=0.0,
                reason=f"warming up crypto scalp history {len(prices)}/{required}",
            )

        trend = _crypto_trend_snapshot(list(prices), self.fast_period, self.slow_period, self.rsi_period)

        if (
            trend.edge_pct >= self.min_edge_pct
            and trend.tick_move_pct > 0
            and self.buy_rsi_min <= trend.rsi <= self.buy_rsi_max
        ):
            self.entry_price[symbol] = quote.price
            self.peak_price[symbol] = quote.price
            confidence = min(trend.edge_pct / max(self.min_edge_pct * 2, 0.01), 1.0)
            return Decision(
                symbol=symbol,
                action="BUY",
                confidence=confidence,
                reason=(
                    f"crypto scalp entry fast={trend.fast_ema:.4f} slow={trend.slow_ema:.4f} "
                    f"edge={trend.edge_pct:.2f}% rsi={trend.rsi:.1f} tick={trend.tick_move_pct:.2f}%"
                ),
                target_dollars=self.target_dollars,
            )

        return Decision(
            symbol=symbol,
            action="HOLD",
            confidence=0.0,
            reason=(
                f"no scalp entry fast={trend.fast_ema:.4f} slow={trend.slow_ema:.4f} "
                f"edge={trend.edge_pct:.2f}% rsi={trend.rsi:.1f} tick={trend.tick_move_pct:.2f}%"
            ),
        )

    def _evaluate_exit(self, symbol: str, price: float, entry: float, peak_price: float) -> Decision:
        peak = max(peak_price, price)
        self.peak_price[symbol] = peak
        pnl_pct = ((price - entry) / entry) * 100.0
        drawdown_pct = ((price - peak) / peak) * 100.0 if peak > 0 else 0.0

        should_sell = False
        reason = ""
        if pnl_pct >= self.take_profit_pct:
            should_sell = True
            reason = f"crypto scalp take profit pnl={pnl_pct:.2f}%"
        elif pnl_pct <= self.stop_loss_pct:
            should_sell = True
            reason = f"crypto scalp stop loss pnl={pnl_pct:.2f}%"
        elif drawdown_pct <= -self.trailing_stop_pct and pnl_pct > self.min_edge_pct:
            should_sell = True
            reason = f"crypto scalp trailing stop pnl={pnl_pct:.2f}% drawdown={drawdown_pct:.2f}%"

        if should_sell:
            self.entry_price.pop(symbol, None)
            self.peak_price.pop(symbol, None)
            return Decision(
                symbol=symbol,
                action="SELL",
                confidence=1.0,
                reason=reason,
            )

        return Decision(
            symbol=symbol,
            action="HOLD",
            confidence=0.0,
            reason=f"holding scalp pnl={pnl_pct:.2f}% drawdown={drawdown_pct:.2f}%",
        )


def build_strategy(name: str, target_dollars: float = 10.0):
    """Create a strategy by config name."""

    normalized = name.strip().lower()
    if normalized == "simple_momentum":
        return SimpleMomentumStrategy(target_dollars=target_dollars)
    if normalized == "crypto_scalp":
        return CryptoScalpStrategy(target_dollars=target_dollars)
    if normalized in {"daily_trend_follow", "daily_trend"}:
        return DailyTrendFollowStrategy(target_dollars=target_dollars)
    if normalized in {"hold", "none"}:
        return HoldStrategy()
    raise ValueError(f"unknown strategy: {name}")


def _ema(values: list[float]) -> float:
    if not values:
        return 0.0

    alpha = 2.0 / (len(values) + 1.0)
    current = values[0]
    for value in values[1:]:
        current = (value * alpha) + (current * (1.0 - alpha))
    return current


def _crypto_trend_snapshot(
    prices: list[float],
    fast_period: int,
    slow_period: int,
    rsi_period: int,
) -> CryptoTrendSnapshot:
    fast = _ema(prices[-fast_period:])
    slow = _ema(prices[-slow_period:])
    previous = prices[-2]
    current = prices[-1]
    tick_move_pct = ((current - previous) / previous) * 100.0 if previous > 0 else 0.0
    edge_pct = ((fast - slow) / slow) * 100.0 if slow > 0 else 0.0
    return CryptoTrendSnapshot(
        fast_ema=fast,
        slow_ema=slow,
        rsi=_rsi(prices, rsi_period),
        tick_move_pct=tick_move_pct,
        edge_pct=edge_pct,
    )


def _first_positive(*values: float | None) -> float:
    for value in values:
        if value is not None and value > 0:
            return float(value)
    return 0.0


def _rsi(values: list[float], period: int) -> float:
    if len(values) < period + 1:
        return 50.0

    window = values[-(period + 1) :]
    gains = []
    losses = []
    for previous, current in zip(window, window[1:], strict=False):
        delta = current - previous
        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(delta))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0

    relative_strength = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))
