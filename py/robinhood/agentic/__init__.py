"""Agentic trading bot scaffolding for Robinhood accounts."""

from .backtest import (
    BacktestResult,
    BacktestTrade,
    run_daily_trend_backtest,
    run_daily_trend_portfolio_backtest,
)
from .broker import (
    AccountSnapshot,
    Broker,
    OrderIntent,
    OrderResult,
    OrderReview,
    PaperBroker,
    Position,
)
from .bot import AgenticBot
from .config import (
    AgenticConfig,
    LaneConfig,
    PersonalConfig,
    RiskConfig,
    SymbolConfig,
    load_config,
    load_lanes,
)
from .execution import ExecutionPlan, plan_order_intent
from .market_data import (
    Candle,
    CandleCollector,
    HistoricalMarketDataSource,
    MarketDataSource,
    MarketDataUnavailable,
    QuoteCollector,
    StaticHistoricalMarketDataSource,
    StaticMarketDataSource,
    YahooDailyCandleSource,
    YahooChartMarketDataSource,
)
from .mcp_broker import AgenticMcpEquityBroker, McpToolClient
from .mcp_client import (
    McpClientUnavailable,
    StreamableHttpMcpToolClient,
    decode_mcp_tool_result,
)
from .quotes import JsonQuoteProvider, ManualQuoteProvider, QuoteProvider, QuoteUnavailable
from .session import PaperSession
from .strategy import (
    CryptoScalpStrategy,
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
    "Candle",
    "CandleCollector",
    "CryptoScalpStrategy",
    "DailyTrendFollowStrategy",
    "Decision",
    "HistoricalMarketDataSource",
    "PersonalConfig",
    "JsonQuoteProvider",
    "LaneConfig",
    "MarketDataSource",
    "MarketDataUnavailable",
    "ManualQuoteProvider",
    "AgenticMcpEquityBroker",
    "McpClientUnavailable",
    "McpToolClient",
    "OrderIntent",
    "OrderResult",
    "OrderReview",
    "PaperSession",
    "PaperBroker",
    "Position",
    "ExecutionPlan",
    "QuoteCollector",
    "QuoteProvider",
    "QuoteUnavailable",
    "QuoteSnapshot",
    "RiskConfig",
    "SimpleMomentumStrategy",
    "StaticHistoricalMarketDataSource",
    "StaticMarketDataSource",
    "StreamableHttpMcpToolClient",
    "SymbolConfig",
    "YahooDailyCandleSource",
    "YahooChartMarketDataSource",
    "load_config",
    "load_lanes",
    "decode_mcp_tool_result",
    "plan_order_intent",
    "run_daily_trend_backtest",
    "run_daily_trend_portfolio_backtest",
]
