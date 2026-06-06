"""Paper trading account state."""

from __future__ import annotations

from dataclasses import dataclass, field

from .journal import JournalEntry
from .strategy import QuoteSnapshot


@dataclass
class PaperAccount:
    """Minimal paper account for recording simulated buy/sell fills."""

    cash: float = 10000.0
    positions: dict[str, float] = field(default_factory=dict)

    def apply(self, entry: JournalEntry, quote: QuoteSnapshot) -> str:
        decision = entry.decision
        risk = entry.risk
        if not risk["approved"] or decision["action"] == "HOLD":
            return "no paper fill"

        symbol = decision["symbol"]

        if decision["action"] == "BUY":
            dollars = float(decision.get("target_dollars") or 0)
            if dollars <= 0:
                return "no paper fill"
            dollars = min(dollars, self.cash)
            if dollars <= 0:
                return "insufficient paper cash"
            quantity = dollars / quote.price
            self.cash -= dollars
            self.positions[symbol] = self.positions.get(symbol, 0.0) + quantity
            return f"paper bought {quantity:.6f} {symbol} for ${dollars:.2f}"

        if decision["action"] == "SELL":
            quantity = self.positions.get(symbol, 0.0)
            if quantity <= 0:
                return "no paper position to sell"
            dollars = quantity * quote.price
            self.cash += dollars
            self.positions[symbol] = 0.0
            return f"paper sold {quantity:.6f} {symbol} for ${dollars:.2f}"

        return "no paper fill"
