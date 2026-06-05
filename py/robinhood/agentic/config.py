"""Configuration loading for the agentic trading bot."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SYMBOLS_PATH = Path(__file__).parent / "config" / "symbols.cfg"
PERSONAL_CONFIG_FILENAME = "rh_agentic.json"


@dataclass(frozen=True)
class SymbolConfig:
    """Allowed symbols grouped by asset class."""

    stocks: tuple[str, ...] = ()
    crypto: tuple[str, ...] = ()


@dataclass(frozen=True)
class RiskConfig:
    """Hard limits enforced before any order can be reviewed or placed."""

    max_trade_dollars: float = 25.0
    max_daily_trades: int = 3
    allow_shorts: bool = False
    allow_options: bool = False


@dataclass(frozen=True)
class PersonalConfig:
    """Personal account settings loaded outside the git repo."""

    account_number: str = ""
    dry_run: bool = True
    journal_path: str = "logs/agentic_decisions.jsonl"
    quote_source_path: str = ""
    poll_seconds: float = 60.0
    paper_starting_cash: float = 10000.0


@dataclass(frozen=True)
class AgenticConfig:
    """Runtime config for the first agentic bot pass."""

    account_number: str = ""
    dry_run: bool = True
    journal_path: str = "logs/agentic_decisions.jsonl"
    quote_source_path: str = ""
    poll_seconds: float = 60.0
    paper_starting_cash: float = 10000.0
    symbols: SymbolConfig = field(default_factory=SymbolConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)


def load_symbols(path: Path | str = DEFAULT_SYMBOLS_PATH) -> SymbolConfig:
    """Load allowed symbol lists from JSON config."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return SymbolConfig(
        stocks=tuple(_normalize_symbols(payload.get("stocks", []))),
        crypto=tuple(_normalize_symbols(payload.get("crypto", []))),
    )


def load_config(
    path: Path | str = DEFAULT_SYMBOLS_PATH,
    personal_path: Path | str | None = None,
) -> AgenticConfig:
    """Load tracked defaults and personal settings from outside the repo."""

    symbols = load_symbols(path)
    personal_path = personal_path or get_personal_config_path()
    personal = load_personal_config(personal_path)
    risk = load_risk_config(personal_path)
    return AgenticConfig(
        account_number=personal.account_number,
        dry_run=personal.dry_run,
        journal_path=personal.journal_path,
        quote_source_path=personal.quote_source_path,
        poll_seconds=personal.poll_seconds,
        paper_starting_cash=personal.paper_starting_cash,
        symbols=symbols,
        risk=risk,
    )


def load_personal_config(path: Path | str | None = None) -> PersonalConfig:
    """Load account-specific settings from a non-repo JSON file."""

    path = path or get_personal_config_path()
    payload = _load_optional_json(path)
    return PersonalConfig(
        account_number=str(
            payload.get("account_number")
            or payload.get("DEFAULT_ACCOUNT_NUMBER")
            or ""
        ),
        dry_run=bool(payload.get("dry_run", True)),
        journal_path=str(payload.get("journal_path", "logs/agentic_decisions.jsonl")),
        quote_source_path=str(payload.get("quote_source_path", "")),
        poll_seconds=float(payload.get("poll_seconds", 60.0)),
        paper_starting_cash=float(payload.get("paper_starting_cash", 10000.0)),
    )


def load_risk_config(path: Path | str | None = None) -> RiskConfig:
    """Load personal risk limits, falling back to conservative defaults."""

    path = path or get_personal_config_path()
    payload = _load_optional_json(path).get("risk", {})
    if not isinstance(payload, dict):
        raise ValueError("risk config must be an object")

    defaults = RiskConfig()
    return RiskConfig(
        max_trade_dollars=float(payload.get("max_trade_dollars", defaults.max_trade_dollars)),
        max_daily_trades=int(payload.get("max_daily_trades", defaults.max_daily_trades)),
        allow_shorts=bool(payload.get("allow_shorts", defaults.allow_shorts)),
        allow_options=bool(payload.get("allow_options", defaults.allow_options)),
    )


def get_personal_config_path() -> Path:
    """Resolve the personal config path from SERVICE_ROOT."""

    service_root = os.environ.get("SERVICE_ROOT")
    if not service_root:
        raise RuntimeError("SERVICE_ROOT must be set to the directory containing rh_agentic.json")
    return Path(service_root) / PERSONAL_CONFIG_FILENAME


def _load_optional_json(path: Path | str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return {}

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("config root must be an object")
    return payload


def _normalize_symbols(values: Any) -> list[str]:
    if not isinstance(values, list):
        raise ValueError("symbol groups must be lists")

    symbols: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("symbols must be strings")
        symbol = value.strip().upper()
        if symbol:
            symbols.append(symbol)
    return symbols
