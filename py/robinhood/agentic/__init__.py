"""Agentic trading bot scaffolding for Robinhood accounts."""

from .bot import AgenticBot
from .config import AgenticConfig, PersonalConfig, RiskConfig, SymbolConfig, load_config
from .quotes import JsonQuoteProvider, ManualQuoteProvider, QuoteProvider
from .session import PaperSession
from .strategy import Decision, QuoteSnapshot, SimpleMomentumStrategy

__all__ = [
    "AgenticBot",
    "AgenticConfig",
    "Decision",
    "PersonalConfig",
    "JsonQuoteProvider",
    "ManualQuoteProvider",
    "PaperSession",
    "QuoteProvider",
    "QuoteSnapshot",
    "RiskConfig",
    "SimpleMomentumStrategy",
    "SymbolConfig",
    "load_config",
]
