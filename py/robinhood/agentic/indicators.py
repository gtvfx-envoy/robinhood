"""Reusable technical indicators for deterministic strategies."""

from __future__ import annotations


def ema(values: list[float], period: int) -> float:
    """Return the final exponential moving average for a value series."""

    if period <= 0:
        raise ValueError("EMA period must be positive")
    if not values:
        return 0.0

    alpha = 2.0 / (period + 1.0)
    current = values[0]
    for value in values[1:]:
        current = (value * alpha) + (current * (1.0 - alpha))
    return current


def atr(highs: list[float], lows: list[float], closes: list[float], period: int) -> float:
    """Return average true range over the final period."""

    if period <= 0:
        raise ValueError("ATR period must be positive")
    if not highs or not lows or not closes:
        return 0.0
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("ATR inputs must have matching lengths")
    if len(closes) < 2:
        return max(0.0, highs[-1] - lows[-1])

    ranges: list[float] = []
    start = max(1, len(closes) - period)
    for index in range(start, len(closes)):
        high = highs[index]
        low = lows[index]
        previous_close = closes[index - 1]
        ranges.append(
            max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        )

    return sum(ranges) / len(ranges) if ranges else 0.0


def percent_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return ((current - previous) / previous) * 100.0
