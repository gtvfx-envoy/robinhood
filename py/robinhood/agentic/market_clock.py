"""Market session clock helpers for persistent daemon scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MarketClockStatus:
    state: str
    trade_day: str | None
    now: datetime
    next_wakeup: datetime
    next_open: datetime
    next_close: datetime

    @property
    def trading_allowed(self) -> bool:
        return self.state == "open"

    @property
    def warmup_allowed(self) -> bool:
        return self.state == "warmup"


class MarketClock:
    """Weekday regular-hours market clock for America/New_York sessions."""

    def __init__(
        self,
        timezone: str = "America/New_York",
        open_time: time = time(9, 30),
        close_time: time = time(16, 0),
        pre_open_warmup_minutes: int = 5,
    ):
        if pre_open_warmup_minutes < 0:
            raise ValueError("pre_open_warmup_minutes must be 0 or greater")
        self.tz = ZoneInfo(timezone)
        self.open_time = open_time
        self.close_time = close_time
        self.pre_open_warmup_minutes = pre_open_warmup_minutes

    def status(self, now: datetime | None = None) -> MarketClockStatus:
        now = self._normalize_now(now)
        current_date = now.date()
        next_open = self._next_open(now)
        next_close = self._close_for(next_open.date())

        if not _is_weekday(current_date):
            return MarketClockStatus("closed", None, now, self._warmup_for(next_open.date()), next_open, next_close)

        open_at = self._open_for(current_date)
        close_at = self._close_for(current_date)
        warmup_at = self._warmup_for(current_date)
        trade_day = current_date.isoformat()

        if now < warmup_at:
            return MarketClockStatus("closed", trade_day, now, warmup_at, open_at, close_at)
        if now < open_at:
            return MarketClockStatus("warmup", trade_day, now, open_at, open_at, close_at)
        if now < close_at:
            return MarketClockStatus("open", trade_day, now, now, open_at, close_at)

        next_open = self._next_open(now + timedelta(days=1))
        return MarketClockStatus(
            "after_close",
            trade_day,
            now,
            self._warmup_for(next_open.date()),
            next_open,
            self._close_for(next_open.date()),
        )

    def seconds_until(self, when: datetime, now: datetime | None = None) -> float:
        now = self._normalize_now(now)
        return max(0.0, (when - now).total_seconds())

    def _normalize_now(self, now: datetime | None) -> datetime:
        if now is None:
            return datetime.now(self.tz)
        if now.tzinfo is None:
            return now.replace(tzinfo=self.tz)
        return now.astimezone(self.tz)

    def _next_open(self, now: datetime) -> datetime:
        day = now.date()
        while True:
            if _is_weekday(day):
                open_at = self._open_for(day)
                if now <= open_at:
                    return open_at
            day += timedelta(days=1)

    def _open_for(self, day) -> datetime:
        return datetime.combine(day, self.open_time, self.tz)

    def _close_for(self, day) -> datetime:
        return datetime.combine(day, self.close_time, self.tz)

    def _warmup_for(self, day) -> datetime:
        return self._open_for(day) - timedelta(minutes=self.pre_open_warmup_minutes)


def _is_weekday(day) -> bool:
    return day.weekday() < 5
