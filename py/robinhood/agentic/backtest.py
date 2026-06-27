"""Simple daily-candle backtesting for agentic strategies."""

from __future__ import annotations

from dataclasses import dataclass, field

from .market_data import Candle
from .strategy import DailyTrendFollowStrategy


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    date: str
    side: str
    quantity: float
    price: float
    dollars: float
    reason: str


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    starting_cash: float
    ending_cash: float
    ending_value: float
    total_return_pct: float
    buy_hold_return_pct: float
    max_drawdown_pct: float
    trades: tuple[BacktestTrade, ...] = ()
    equity_curve: tuple[float, ...] = field(default_factory=tuple)


@dataclass
class _Position:
    quantity: float = 0.0
    entry_price: float = 0.0
    peak_price: float = 0.0


def run_daily_trend_backtest(
    symbol: str,
    candles: tuple[Candle, ...] | list[Candle],
    starting_cash: float = 100.0,
    target_dollars: float = 10.0,
    min_order_dollars: float = 1.0,
    max_trade_dollars: float = 15.0,
    min_cash_reserve: float = 50.0,
    slippage_pct: float = 0.05,
    strategy: DailyTrendFollowStrategy | None = None,
) -> BacktestResult:
    """Run a long-only daily trend backtest on one symbol."""

    ordered = tuple(sorted(candles, key=lambda candle: candle.date))
    if not ordered:
        raise ValueError("backtest requires at least one candle")

    normalized = symbol.upper()
    strategy = strategy or DailyTrendFollowStrategy(
        target_dollars=min(target_dollars, max_trade_dollars)
    )
    cash = starting_cash
    position = _Position()
    trades: list[BacktestTrade] = []
    equity_curve: list[float] = []

    for index, candle in enumerate(ordered):
        history = ordered[: index + 1]
        has_position = position.quantity > 0
        decision = strategy.evaluate_candles(
            normalized,
            history,
            has_position=has_position,
            entry_price=position.entry_price if has_position else None,
            peak_price=position.peak_price if has_position else None,
        )

        if decision.action == "BUY" and not has_position:
            trade_dollars = min(
                float(decision.target_dollars or target_dollars),
                max_trade_dollars,
                max(0.0, cash - min_cash_reserve),
            )
            if trade_dollars >= min_order_dollars:
                fill_price = candle.close * (1.0 + (slippage_pct / 100.0))
                quantity = trade_dollars / fill_price
                cash -= trade_dollars
                position = _Position(
                    quantity=quantity,
                    entry_price=fill_price,
                    peak_price=candle.close,
                )
                trades.append(
                    BacktestTrade(
                        symbol=normalized,
                        date=candle.date.isoformat(),
                        side="BUY",
                        quantity=quantity,
                        price=fill_price,
                        dollars=trade_dollars,
                        reason=decision.reason,
                    )
                )

        elif decision.action == "SELL" and has_position:
            fill_price = candle.close * (1.0 - (slippage_pct / 100.0))
            dollars = position.quantity * fill_price
            cash += dollars
            trades.append(
                BacktestTrade(
                    symbol=normalized,
                    date=candle.date.isoformat(),
                    side="SELL",
                    quantity=position.quantity,
                    price=fill_price,
                    dollars=dollars,
                    reason=decision.reason,
                )
            )
            position = _Position()

        if position.quantity > 0:
            position.peak_price = max(position.peak_price, candle.close)

        equity_curve.append(cash + (position.quantity * candle.close))

    ending_value = equity_curve[-1]
    total_return_pct = _return_pct(ending_value, starting_cash)
    buy_hold_return_pct = _return_pct(ordered[-1].close, ordered[0].close)
    return BacktestResult(
        symbol=normalized,
        starting_cash=starting_cash,
        ending_cash=cash,
        ending_value=ending_value,
        total_return_pct=total_return_pct,
        buy_hold_return_pct=buy_hold_return_pct,
        max_drawdown_pct=_max_drawdown_pct(equity_curve),
        trades=tuple(trades),
        equity_curve=tuple(equity_curve),
    )


def run_daily_trend_portfolio_backtest(
    candles_by_symbol: dict[str, tuple[Candle, ...] | list[Candle]],
    starting_cash: float = 100.0,
    target_dollars: float = 10.0,
    min_order_dollars: float = 1.0,
    max_trade_dollars: float = 15.0,
    min_cash_reserve: float = 50.0,
    max_open_positions: int = 2,
    max_new_buys_per_day: int = 1,
    max_daily_trades: int = 2,
    max_total_exposure_dollars: float = 50.0,
    slippage_pct: float = 0.05,
) -> BacktestResult:
    """Run a shared-cash daily trend backtest across symbols."""

    normalized_candles = {
        symbol.upper(): tuple(sorted(candles, key=lambda candle: candle.date))
        for symbol, candles in candles_by_symbol.items()
        if candles
    }
    if not normalized_candles:
        raise ValueError("portfolio backtest requires candles")

    all_dates = sorted({candle.date for candles in normalized_candles.values() for candle in candles})
    strategies = {
        symbol: DailyTrendFollowStrategy(target_dollars=min(target_dollars, max_trade_dollars))
        for symbol in normalized_candles
    }
    cash = starting_cash
    positions: dict[str, _Position] = {}
    trades: list[BacktestTrade] = []
    equity_curve: list[float] = []

    for current_date in all_dates:
        daily_trades = 0
        daily_buys = 0
        closes = _latest_closes_by_date(normalized_candles, current_date)

        for symbol in sorted(tuple(positions)):
            if daily_trades >= max_daily_trades:
                break
            history = _candles_through(normalized_candles[symbol], current_date)
            if not history:
                continue
            position = positions[symbol]
            candle = history[-1]
            decision = strategies[symbol].evaluate_candles(
                symbol,
                history,
                has_position=True,
                entry_price=position.entry_price,
                peak_price=position.peak_price,
            )
            if decision.action != "SELL":
                position.peak_price = max(position.peak_price, candle.close)
                continue

            fill_price = candle.close * (1.0 - (slippage_pct / 100.0))
            dollars = position.quantity * fill_price
            cash += dollars
            trades.append(
                BacktestTrade(
                    symbol=symbol,
                    date=current_date.isoformat(),
                    side="SELL",
                    quantity=position.quantity,
                    price=fill_price,
                    dollars=dollars,
                    reason=decision.reason,
                )
            )
            positions.pop(symbol, None)
            daily_trades += 1

        for symbol in sorted(normalized_candles):
            if daily_trades >= max_daily_trades or daily_buys >= max_new_buys_per_day:
                break
            if symbol in positions or len(positions) >= max_open_positions:
                continue
            history = _candles_through(normalized_candles[symbol], current_date)
            if not history:
                continue
            candle = history[-1]
            decision = strategies[symbol].evaluate_candles(symbol, history)
            if decision.action != "BUY":
                continue

            current_exposure = _portfolio_exposure(positions, closes)
            exposure_room = (
                max_total_exposure_dollars - current_exposure
                if max_total_exposure_dollars > 0
                else starting_cash
            )
            trade_dollars = min(
                float(decision.target_dollars or target_dollars),
                max_trade_dollars,
                max(0.0, cash - min_cash_reserve),
                max(0.0, exposure_room),
            )
            if trade_dollars < min_order_dollars:
                continue

            fill_price = candle.close * (1.0 + (slippage_pct / 100.0))
            quantity = trade_dollars / fill_price
            cash -= trade_dollars
            positions[symbol] = _Position(
                quantity=quantity,
                entry_price=fill_price,
                peak_price=candle.close,
            )
            trades.append(
                BacktestTrade(
                    symbol=symbol,
                    date=current_date.isoformat(),
                    side="BUY",
                    quantity=quantity,
                    price=fill_price,
                    dollars=trade_dollars,
                    reason=decision.reason,
                )
            )
            daily_trades += 1
            daily_buys += 1

        equity_curve.append(cash + _portfolio_exposure(positions, closes))

    ending_value = equity_curve[-1]
    return BacktestResult(
        symbol="PORTFOLIO",
        starting_cash=starting_cash,
        ending_cash=cash,
        ending_value=ending_value,
        total_return_pct=_return_pct(ending_value, starting_cash),
        buy_hold_return_pct=_equal_weight_buy_hold_return_pct(normalized_candles),
        max_drawdown_pct=_max_drawdown_pct(equity_curve),
        trades=tuple(trades),
        equity_curve=tuple(equity_curve),
    )


def _return_pct(current: float, start: float) -> float:
    if start <= 0:
        return 0.0
    return ((current - start) / start) * 100.0


def _max_drawdown_pct(values: list[float]) -> float:
    if not values:
        return 0.0

    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = _return_pct(value, peak)
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


def _candles_through(candles: tuple[Candle, ...], current_date) -> tuple[Candle, ...]:
    return tuple(candle for candle in candles if candle.date <= current_date)


def _latest_closes_by_date(candles_by_symbol: dict[str, tuple[Candle, ...]], current_date) -> dict[str, float]:
    closes: dict[str, float] = {}
    for symbol, candles in candles_by_symbol.items():
        history = _candles_through(candles, current_date)
        if history:
            closes[symbol] = history[-1].close
    return closes


def _portfolio_exposure(positions: dict[str, _Position], closes: dict[str, float]) -> float:
    return sum(position.quantity * closes.get(symbol, position.entry_price) for symbol, position in positions.items())


def _equal_weight_buy_hold_return_pct(candles_by_symbol: dict[str, tuple[Candle, ...]]) -> float:
    returns = [
        _return_pct(candles[-1].close, candles[0].close)
        for candles in candles_by_symbol.values()
        if candles and candles[0].close > 0
    ]
    if not returns:
        return 0.0
    return sum(returns) / len(returns)
