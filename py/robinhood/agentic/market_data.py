"""Market data sources and quote collection."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .strategy import QuoteSnapshot


@dataclass(frozen=True)
class Candle:
    """Daily OHLCV candle used by backtests and slower strategies."""

    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class MarketDataUnavailable(Exception):
    """Raised when market data cannot be collected for a symbol."""


class MarketDataSource(ABC):
    """Interface for sources that collect fresh market quote data."""

    @abstractmethod
    def get_quote(self, symbol: str) -> QuoteSnapshot:
        """Collect one current quote snapshot."""


class HistoricalMarketDataSource(ABC):
    """Interface for historical OHLCV collection."""

    @abstractmethod
    def get_daily_candles(self, symbol: str, range_: str = "1y") -> tuple[Candle, ...]:
        """Collect daily candles for a symbol."""


class ValidatedHistoricalMarketDataSource(HistoricalMarketDataSource):
    """Validate primary data and fail over to a separately configured source."""

    def __init__(
        self,
        primary: HistoricalMarketDataSource,
        fallback: HistoricalMarketDataSource | None = None,
        max_staleness_days: int = 5,
        today_fn=None,
    ):
        self.primary = primary
        self.fallback = fallback
        self.max_staleness_days = max_staleness_days
        self.today_fn = today_fn or date.today

    def get_daily_candles(self, symbol: str, range_: str = "1y") -> tuple[Candle, ...]:
        errors: list[str] = []
        for source in (self.primary, self.fallback):
            if source is None:
                continue
            try:
                candles = source.get_daily_candles(symbol, range_)
                validate_daily_candles(candles, self.max_staleness_days, self.today_fn())
                return candles
            except MarketDataUnavailable as exc:
                errors.append(str(exc))
        raise MarketDataUnavailable(f"validated candles unavailable for {symbol}: {' | '.join(errors)}")


def validate_daily_candles(candles: tuple[Candle, ...], max_staleness_days: int, today: date) -> None:
    """Reject stale, future-dated, unordered, or impossible OHLC data."""

    if not candles:
        raise MarketDataUnavailable("no daily candles returned")
    if max_staleness_days < 0:
        raise ValueError("max_staleness_days must be non-negative")
    previous: date | None = None
    for candle in candles:
        if previous is not None and candle.date <= previous:
            raise MarketDataUnavailable("daily candles must have strictly increasing dates")
        if min(candle.open, candle.high, candle.low, candle.close) <= 0:
            raise MarketDataUnavailable("daily candles must have positive OHLC values")
        if candle.low > min(candle.open, candle.close) or candle.high < max(candle.open, candle.close):
            raise MarketDataUnavailable("daily candle OHLC values are inconsistent")
        previous = candle.date
    if candles[-1].date > today:
        raise MarketDataUnavailable("daily candle timestamp is in the future")
    if today - candles[-1].date > timedelta(days=max_staleness_days):
        raise MarketDataUnavailable(f"daily candles are stale: last={candles[-1].date.isoformat()}")


class YahooChartMarketDataSource(MarketDataSource):
    """Collect quotes from Yahoo's public chart endpoint using stdlib HTTP."""

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        yahoo_symbol = _to_yahoo_symbol(symbol)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(yahoo_symbol)}?range=1d&interval=1d"
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            raise MarketDataUnavailable(
                f"failed to fetch quote for {symbol}: HTTP {exc.code} {exc.reason}: {body}"
            ) from exc
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise MarketDataUnavailable(f"failed to fetch quote for {symbol}: {exc}") from exc

        try:
            meta = payload["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            previous_close = meta.get("chartPreviousClose") or meta.get("previousClose")
        except (KeyError, IndexError, TypeError) as exc:
            raise MarketDataUnavailable(f"unexpected quote response for {symbol}") from exc

        if price is None:
            raise MarketDataUnavailable(f"quote for {symbol} did not include price")

        return QuoteSnapshot(
            symbol=symbol.upper(),
            price=float(price),
            previous_close=float(previous_close) if previous_close is not None else None,
        )


class YahooDailyCandleSource(HistoricalMarketDataSource):
    """Collect daily candles from Yahoo's public chart endpoint."""

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds

    def get_daily_candles(self, symbol: str, range_: str = "1y") -> tuple[Candle, ...]:
        yahoo_symbol = _to_yahoo_symbol(symbol)
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(yahoo_symbol)}?range={quote(range_)}&interval=1d"
        )
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            raise MarketDataUnavailable(
                f"failed to fetch candles for {symbol}: HTTP {exc.code} {exc.reason}: {body}"
            ) from exc
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise MarketDataUnavailable(f"failed to fetch candles for {symbol}: {exc}") from exc

        try:
            result = payload["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote_payload = result["indicators"]["quote"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise MarketDataUnavailable(f"unexpected candle response for {symbol}") from exc

        candles: list[Candle] = []
        for index, timestamp in enumerate(timestamps):
            try:
                open_ = quote_payload["open"][index]
                high = quote_payload["high"][index]
                low = quote_payload["low"][index]
                close = quote_payload["close"][index]
                volume = quote_payload.get("volume", [0.0] * len(timestamps))[index]
            except (IndexError, TypeError) as exc:
                raise MarketDataUnavailable(f"invalid candle response for {symbol}") from exc

            if None in {open_, high, low, close}:
                continue
            candles.append(
                Candle(
                    symbol=symbol.upper(),
                    date=datetime.utcfromtimestamp(timestamp).date(),
                    open=float(open_),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=float(volume or 0.0),
                )
            )

        if not candles:
            raise MarketDataUnavailable(f"no daily candles returned for {symbol}")
        return tuple(candles)


class StaticMarketDataSource(MarketDataSource):
    """Test/dry-run source backed by an in-memory mapping."""

    def __init__(self, quotes: dict[str, QuoteSnapshot]):
        self.quotes = {symbol.upper(): quote for symbol, quote in quotes.items()}

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        quote = self.quotes.get(symbol.upper())
        if quote is None:
            raise MarketDataUnavailable(f"quote for {symbol.upper()} not found")
        return quote


class StaticHistoricalMarketDataSource(HistoricalMarketDataSource):
    """Test source backed by in-memory candles."""

    def __init__(self, candles: dict[str, tuple[Candle, ...]]):
        self.candles = {symbol.upper(): tuple(values) for symbol, values in candles.items()}

    def get_daily_candles(self, symbol: str, range_: str = "1y") -> tuple[Candle, ...]:
        values = self.candles.get(symbol.upper())
        if values is None:
            raise MarketDataUnavailable(f"candles for {symbol.upper()} not found")
        return values


class QuoteCollector:
    """Collect quotes and maintain the JSON quote cache used for inspection."""

    def __init__(self, source: MarketDataSource, cache_path: Path | str):
        self.source = source
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def collect(self, symbols: Iterable[str]) -> tuple[dict[str, QuoteSnapshot], dict[str, str]]:
        quotes: dict[str, QuoteSnapshot] = {}
        errors: dict[str, str] = {}

        for symbol in symbols:
            normalized = symbol.upper()
            try:
                quotes[normalized] = self.source.get_quote(normalized)
            except MarketDataUnavailable as exc:
                errors[normalized] = str(exc)

        if quotes:
            self._write_cache(quotes)
        elif not self.cache_path.exists():
            self.cache_path.write_text("{}", encoding="utf-8")

        return quotes, errors

    def _write_cache(self, quotes: dict[str, QuoteSnapshot]) -> None:
        existing = _load_existing_cache(self.cache_path)
        symbols = existing.setdefault("symbols", {})
        for symbol, snapshot in quotes.items():
            payload = asdict(snapshot)
            payload["timestamp"] = _format_timestamp(snapshot.timestamp)
            symbols[symbol] = payload

        self.cache_path.write_text(
            json.dumps(existing, indent=2, sort_keys=True),
            encoding="utf-8",
        )


class CandleCollector:
    """Collect daily candles and maintain a JSON cache."""

    def __init__(self, source: HistoricalMarketDataSource, cache_path: Path | str):
        self.source = source
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def collect(
        self, symbols: Iterable[str], range_: str = "1y"
    ) -> tuple[dict[str, tuple[Candle, ...]], dict[str, str]]:
        candles: dict[str, tuple[Candle, ...]] = {}
        errors: dict[str, str] = {}

        for symbol in symbols:
            normalized = symbol.upper()
            try:
                candles[normalized] = self.source.get_daily_candles(normalized, range_=range_)
            except MarketDataUnavailable as exc:
                errors[normalized] = str(exc)

        if candles:
            self._write_cache(candles)
        elif not self.cache_path.exists():
            self.cache_path.write_text("{}", encoding="utf-8")

        return candles, errors

    def _write_cache(self, candles: dict[str, tuple[Candle, ...]]) -> None:
        existing = _load_existing_cache(self.cache_path)
        symbols = existing.setdefault("symbols", {})
        for symbol, values in candles.items():
            symbols[symbol] = [_candle_to_json(candle) for candle in values]

        self.cache_path.write_text(
            json.dumps(existing, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _load_existing_cache(path: Path) -> dict:
    if not path.exists():
        return {"symbols": {}}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"symbols": {}}

    if not isinstance(payload, dict):
        return {"symbols": {}}
    if "symbols" not in payload:
        return {"symbols": payload}
    if not isinstance(payload["symbols"], dict):
        payload["symbols"] = {}
    return payload


def _format_timestamp(value: datetime) -> str:
    return value.isoformat()


def _candle_to_json(candle: Candle) -> dict:
    payload = asdict(candle)
    payload["date"] = candle.date.isoformat()
    return payload


def _to_yahoo_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if "-" in normalized:
        return normalized
    if normalized in {"BTC", "ETH", "SOL", "DOGE", "ADA"}:
        return f"{normalized}-USD"
    return normalized
