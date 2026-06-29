"""Configuration loading for the agentic trading bot."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_SYMBOLS_PATH = Path(__file__).parent / "config" / "symbols.cfg"
PERSONAL_CONFIG_FILENAME = "rh_agentic.json"
LIVE_ORDER_CONFIRMATION = "I_UNDERSTAND_THIS_CAN_PLACE_REAL_ORDERS"


@dataclass(frozen=True)
class SymbolConfig:
    """Allowed symbols grouped by asset class."""

    stocks: tuple[str, ...] = ()
    crypto: tuple[str, ...] = ()


@dataclass(frozen=True)
class LaneConfig:
    """A configurable analysis lane with its own symbols and cadence."""

    name: str
    symbols: tuple[str, ...] = ()
    strategy: str = "simple_momentum"
    poll_seconds: float = 60.0
    asset_class: str = "equity"


@dataclass(frozen=True)
class RiskConfig:
    """Hard limits enforced before any order can be reviewed or placed."""

    min_order_dollars: float = 1.0
    max_trade_dollars: float = 25.0
    max_daily_trades: int = 3
    max_new_buys_per_day: int = 1
    max_open_positions: int = 2
    min_cash_reserve: float = 0.0
    max_total_exposure_dollars: float = 0.0
    allow_shorts: bool = False
    allow_options: bool = False


@dataclass(frozen=True)
class PersonalConfig:
    """Personal account settings loaded outside the git repo."""

    account_number: str = ""
    broker: str = "paper"
    mcp_url: str = "https://agent.robinhood.com/mcp/trading"
    mcp_bearer_token_env_var: str = ""
    mcp_token_store_path: str = ""
    mcp_oauth_callback_port: int = 8765
    mcp_oauth_scope: str = ""
    dry_run: bool = True
    live_trading_enabled: bool = False
    auto_place_orders: bool = False
    live_order_confirm: str = ""
    journal_path: str = "logs/agentic_decisions.jsonl"
    quote_source_path: str = ""
    poll_seconds: float = 60.0
    paper_starting_cash: float = 10000.0


@dataclass(frozen=True)
class AgenticConfig:
    """Runtime config for the first agentic bot pass."""

    account_number: str = ""
    broker: str = "paper"
    mcp_url: str = "https://agent.robinhood.com/mcp/trading"
    mcp_bearer_token_env_var: str = ""
    mcp_token_store_path: str = ""
    mcp_oauth_callback_port: int = 8765
    mcp_oauth_scope: str = ""
    dry_run: bool = True
    live_trading_enabled: bool = False
    auto_place_orders: bool = False
    live_order_confirm: str = ""
    journal_path: str = "logs/agentic_decisions.jsonl"
    quote_source_path: str = ""
    poll_seconds: float = 60.0
    paper_starting_cash: float = 10000.0
    symbols: SymbolConfig = field(default_factory=SymbolConfig)
    lanes: tuple[LaneConfig, ...] = ()
    risk: RiskConfig = field(default_factory=RiskConfig)


def load_symbols(path: Path | str = DEFAULT_SYMBOLS_PATH) -> SymbolConfig:
    """Load allowed symbol lists from JSON config."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return SymbolConfig(
        stocks=tuple(_normalize_symbols(_lane_symbols(payload.get("stocks", [])))),
        crypto=tuple(_normalize_symbols(_lane_symbols(payload.get("crypto", [])))),
    )


def load_lanes(path: Path | str = DEFAULT_SYMBOLS_PATH) -> tuple[LaneConfig, ...]:
    """Load configured analysis lanes from repo config."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("lane config root must be an object")

    lanes: list[LaneConfig] = []
    for name, raw_lane in payload.items():
        lane = _load_lane(name, raw_lane)
        if lane.symbols:
            lanes.append(lane)
    return tuple(lanes)


def load_config(
    path: Path | str = DEFAULT_SYMBOLS_PATH,
    personal_path: Path | str | None = None,
) -> AgenticConfig:
    """Load tracked defaults and personal settings from outside the repo."""

    symbols = load_symbols(path)
    lanes = load_lanes(path)
    personal_path = personal_path or get_personal_config_path()
    personal = load_personal_config(personal_path)
    risk = load_risk_config(personal_path)
    return AgenticConfig(
        account_number=personal.account_number,
        broker=personal.broker,
        mcp_url=personal.mcp_url,
        mcp_bearer_token_env_var=personal.mcp_bearer_token_env_var,
        mcp_token_store_path=personal.mcp_token_store_path,
        mcp_oauth_callback_port=personal.mcp_oauth_callback_port,
        mcp_oauth_scope=personal.mcp_oauth_scope,
        dry_run=personal.dry_run,
        live_trading_enabled=personal.live_trading_enabled,
        auto_place_orders=personal.auto_place_orders,
        live_order_confirm=personal.live_order_confirm,
        journal_path=personal.journal_path,
        quote_source_path=personal.quote_source_path,
        poll_seconds=personal.poll_seconds,
        paper_starting_cash=personal.paper_starting_cash,
        symbols=symbols,
        lanes=lanes,
        risk=risk,
    )


def load_personal_config(path: Path | str | None = None) -> PersonalConfig:
    """Load account-specific settings from a non-repo JSON file."""

    path = path or get_personal_config_path()
    payload = _load_optional_json(path)
    return PersonalConfig(
        account_number=str(payload.get("account_number") or payload.get("DEFAULT_ACCOUNT_NUMBER") or ""),
        dry_run=bool(payload.get("dry_run", True)),
        broker=str(payload.get("broker", "paper")),
        mcp_url=str(payload.get("mcp_url", "https://agent.robinhood.com/mcp/trading")),
        mcp_bearer_token_env_var=str(payload.get("mcp_bearer_token_env_var", "")),
        mcp_token_store_path=str(payload.get("mcp_token_store_path", "")),
        mcp_oauth_callback_port=int(payload.get("mcp_oauth_callback_port", 8765)),
        mcp_oauth_scope=str(payload.get("mcp_oauth_scope", "")),
        live_trading_enabled=bool(payload.get("live_trading_enabled", False)),
        auto_place_orders=bool(payload.get("auto_place_orders", False)),
        live_order_confirm=str(payload.get("live_order_confirm", "")),
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
        min_order_dollars=float(payload.get("min_order_dollars", defaults.min_order_dollars)),
        max_trade_dollars=float(payload.get("max_trade_dollars", defaults.max_trade_dollars)),
        max_daily_trades=int(payload.get("max_daily_trades", defaults.max_daily_trades)),
        max_new_buys_per_day=int(payload.get("max_new_buys_per_day", defaults.max_new_buys_per_day)),
        max_open_positions=int(payload.get("max_open_positions", defaults.max_open_positions)),
        min_cash_reserve=float(payload.get("min_cash_reserve", defaults.min_cash_reserve)),
        max_total_exposure_dollars=float(
            payload.get("max_total_exposure_dollars", defaults.max_total_exposure_dollars)
        ),
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


def _lane_symbols(raw_lane: Any) -> Any:
    if isinstance(raw_lane, dict):
        return raw_lane.get("symbols", [])
    return raw_lane


def _load_lane(name: str, raw_lane: Any) -> LaneConfig:
    if isinstance(raw_lane, list):
        return LaneConfig(name=name, symbols=tuple(_normalize_symbols(raw_lane)))

    if not isinstance(raw_lane, dict):
        raise ValueError(f"lane {name} must be a list or object")

    return LaneConfig(
        name=name,
        symbols=tuple(_normalize_symbols(raw_lane.get("symbols", []))),
        strategy=str(raw_lane.get("strategy", "simple_momentum")),
        poll_seconds=float(raw_lane.get("poll_seconds", 60.0)),
        asset_class=str(raw_lane.get("asset_class", name)),
    )
