"""Quote providers for agentic analysis sessions."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Any

from .strategy import QuoteSnapshot


class QuoteProvider(ABC):
    """Interface for collecting quote snapshots from a data source."""

    @abstractmethod
    def get_quote(self, symbol: str) -> QuoteSnapshot:
        """Return the latest quote snapshot for a symbol."""


class ManualQuoteProvider(QuoteProvider):
    """One-shot provider used by tests and CLI smoke checks."""

    def __init__(self, price: float, previous_close: float | None = None):
        self.price = price
        self.previous_close = previous_close

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        return QuoteSnapshot(
            symbol=symbol,
            price=self.price,
            previous_close=self.previous_close,
        )


class JsonQuoteProvider(QuoteProvider):
    """Read latest quotes from a JSON file written by a collector process.

    Supported shapes:
      {"AAPL": {"price": 205, "previous_close": 200}}
      {"symbols": {"AAPL": {"price": 205, "previous_close": 200}}}
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        symbols = payload.get("symbols", payload)
        if not isinstance(symbols, dict):
            raise ValueError("quote file must contain a symbol mapping")

        quote = symbols.get(symbol.upper())
        if not isinstance(quote, dict):
            raise KeyError(f"quote for {symbol.upper()} not found in {self.path}")

        return QuoteSnapshot(
            symbol=symbol.upper(),
            price=float(_required(quote, "price")),
            previous_close=_optional_float(quote.get("previous_close")),
        )


def _required(payload: dict[str, Any], key: str) -> Any:
    if key not in payload:
        raise ValueError(f"quote field required: {key}")
    return payload[key]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
