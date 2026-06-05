"""Market data sources and quote collection."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .strategy import QuoteSnapshot


class MarketDataUnavailable(Exception):
    """Raised when market data cannot be collected for a symbol."""


class MarketDataSource(ABC):
    """Interface for sources that collect fresh market quote data."""

    @abstractmethod
    def get_quote(self, symbol: str) -> QuoteSnapshot:
        """Collect one current quote snapshot."""


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


class StaticMarketDataSource(MarketDataSource):
    """Test/dry-run source backed by an in-memory mapping."""

    def __init__(self, quotes: dict[str, QuoteSnapshot]):
        self.quotes = {symbol.upper(): quote for symbol, quote in quotes.items()}

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        quote = self.quotes.get(symbol.upper())
        if quote is None:
            raise MarketDataUnavailable(f"quote for {symbol.upper()} not found")
        return quote


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


def _to_yahoo_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if "-" in normalized:
        return normalized
    if normalized in {"BTC", "ETH", "SOL", "DOGE", "ADA"}:
        return f"{normalized}-USD"
    return normalized
