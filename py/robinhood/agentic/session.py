"""Persistent paper-trading session runner."""

from __future__ import annotations

from dataclasses import dataclass
import time

from .bot import AgenticBot
from .config import AgenticConfig
from .paper import PaperAccount
from .quotes import QuoteProvider


@dataclass(frozen=True)
class SessionResult:
    iterations: int
    decisions: int
    paper_cash: float
    positions: dict[str, float]


class PaperSession:
    """Poll quote data, analyze configured symbols, and simulate fills."""

    def __init__(
        self,
        config: AgenticConfig,
        quote_provider: QuoteProvider,
        bot: AgenticBot | None = None,
        paper_account: PaperAccount | None = None,
    ):
        self.config = config
        self.quote_provider = quote_provider
        self.bot = bot or AgenticBot(config)
        self.paper_account = paper_account or PaperAccount(config.paper_starting_cash)

    def run(self, max_iterations: int | None = None) -> SessionResult:
        iterations = 0
        decisions = 0

        while max_iterations is None or iterations < max_iterations:
            iterations += 1
            for symbol in self.config.symbols.stocks:
                quote = self.quote_provider.get_quote(symbol)
                entry = self.bot.analyze(quote)
                decisions += 1
                fill = self.paper_account.apply(entry, quote)
                decision = entry.decision
                print(f"{symbol}: {decision['action']} - {entry.risk['reason']} - {fill}")

            if max_iterations is not None and iterations >= max_iterations:
                break
            time.sleep(self.config.poll_seconds)

        return SessionResult(
            iterations=iterations,
            decisions=decisions,
            paper_cash=self.paper_account.cash,
            positions=dict(self.paper_account.positions),
        )
