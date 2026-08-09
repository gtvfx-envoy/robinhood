"""Agentic trading bot scaffolding for Robinhood accounts."""

from .backtest import (
    BacktestResult,
    BacktestTrade,
    run_daily_trend_backtest,
    run_daily_trend_portfolio_backtest,
)
from .bot import AgenticBot
from .broker import (
    AccountSnapshot,
    Broker,
    OrderIntent,
    OrderResult,
    OrderReview,
    PaperBroker,
    Position,
)
from .config import (
    AgenticConfig,
    LaneConfig,
    PersonalConfig,
    RiskConfig,
    SymbolConfig,
    load_config,
    load_lanes,
)
from .daemon import PersistentDaemon, StateBackedBroker
from .daemon_state import DaemonLease, DaemonState, DaemonStateStore, PendingOrderState
from .execution import ExecutionPlan, plan_order_intent
from .market_clock import MarketCalendar, MarketClock, MarketClockStatus
from .market_data import (
    Candle,
    CandleCollector,
    HistoricalMarketDataSource,
    MarketDataSource,
    MarketDataUnavailable,
    QuoteCollector,
    StaticHistoricalMarketDataSource,
    StaticMarketDataSource,
    ValidatedHistoricalMarketDataSource,
    YahooChartMarketDataSource,
    YahooDailyCandleSource,
    validate_daily_candles,
)
from .mcp_broker import AgenticMcpEquityBroker, McpToolClient
from .mcp_client import (
    McpClientUnavailable,
    StreamableHttpMcpToolClient,
    decode_mcp_tool_result,
)
from .quotes import JsonQuoteProvider, ManualQuoteProvider, QuoteProvider, QuoteUnavailable
from .session import BrokerSession, PaperSession
from .strategy import (
    CryptoScalpStrategy,
    CryptoTrendSnapshot,
    DailyTrendFollowStrategy,
    Decision,
    QuoteSnapshot,
    SimpleMomentumStrategy,
)

__all__ = [
    "AgenticBot",
    "AgenticConfig",
    "AccountSnapshot",
    "BacktestResult",
    "BacktestTrade",
    "Broker",
    "BrokerSession",
    "Candle",
    "CandleCollector",
    "CryptoScalpStrategy",
    "CryptoTrendSnapshot",
    "DaemonState",
    "DaemonLease",
    "DaemonStateStore",
    "DailyTrendFollowStrategy",
    "Decision",
    "HistoricalMarketDataSource",
    "PersonalConfig",
    "JsonQuoteProvider",
    "LaneConfig",
    "MarketDataSource",
    "MarketDataUnavailable",
    "MarketCalendar",
    "MarketClock",
    "MarketClockStatus",
    "ManualQuoteProvider",
    "AgenticMcpEquityBroker",
    "McpClientUnavailable",
    "McpToolClient",
    "OrderIntent",
    "OrderResult",
    "OrderReview",
    "PaperSession",
    "PaperBroker",
    "PendingOrderState",
    "PersistentDaemon",
    "Position",
    "ExecutionPlan",
    "QuoteCollector",
    "QuoteProvider",
    "QuoteUnavailable",
    "QuoteSnapshot",
    "RiskConfig",
    "SimpleMomentumStrategy",
    "StateBackedBroker",
    "StaticHistoricalMarketDataSource",
    "StaticMarketDataSource",
    "StreamableHttpMcpToolClient",
    "SymbolConfig",
    "YahooDailyCandleSource",
    "ValidatedHistoricalMarketDataSource",
    "YahooChartMarketDataSource",
    "load_config",
    "load_lanes",
    "decode_mcp_tool_result",
    "plan_order_intent",
    "run_daily_trend_backtest",
    "run_daily_trend_portfolio_backtest",
    "validate_daily_candles",
]
