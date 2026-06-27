"""Command-line entry point for the agentic dry-run bot."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from .backtest import run_daily_trend_backtest, run_daily_trend_portfolio_backtest
from .bot import AgenticBot
from .broker import OrderIntent
from .config import get_personal_config_path, load_config
from .market_data import QuoteCollector, YahooChartMarketDataSource, YahooDailyCandleSource
from .mcp_broker import AgenticMcpEquityBroker
from .mcp_client import StreamableHttpMcpToolClient
from .quotes import JsonQuoteProvider, ManualQuoteProvider
from .session import PaperSession


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an agentic Robinhood dry-run analysis.")
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser("analyze", help="Analyze one symbol once.")
    analyze.add_argument("--symbol", required=True, help="Stock symbol to analyze.")
    analyze.add_argument("--price", type=float, required=True, help="Current price snapshot.")
    analyze.add_argument("--previous-close", type=float, help="Previous close snapshot.")
    _add_common_args(analyze)

    backtest = subparsers.add_parser("backtest", help="Backtest daily trend following.")
    backtest.add_argument("--symbol", action="append", help="Symbol to backtest. May be repeated.")
    backtest.add_argument("--range", default="1y", help="Yahoo chart range, e.g. 6mo, 1y, 2y, 5y.")
    backtest.add_argument("--portfolio", action="store_true", help="Run one shared-cash portfolio backtest.")
    backtest.add_argument("--starting-cash", type=float, default=100.0, help="Starting paper cash.")
    backtest.add_argument("--target-dollars", type=float, default=10.0, help="Target dollars per buy.")
    backtest.add_argument("--min-order-dollars", type=float, help="Override minimum trade notional.")
    backtest.add_argument("--max-trade-dollars", type=float, help="Override maximum trade notional.")
    backtest.add_argument("--min-cash-reserve", type=float, help="Override minimum cash reserve.")
    backtest.add_argument("--max-open-positions", type=int, help="Override maximum open positions.")
    backtest.add_argument("--max-new-buys-per-day", type=int, help="Override maximum new buys per day.")
    backtest.add_argument("--max-daily-trades", type=int, help="Override maximum total trades per day.")
    backtest.add_argument("--max-total-exposure-dollars", type=float, help="Override maximum deployed capital.")
    backtest.add_argument("--slippage-pct", type=float, default=0.05, help="Per-side slippage percentage.")
    _add_common_args(backtest)

    mcp_check = subparsers.add_parser("mcp-check", help="Check Agentic MCP broker connectivity.")
    mcp_check.add_argument("--symbol", default="SPY", help="Symbol to check tradability for.")
    _add_common_args(mcp_check)

    run = subparsers.add_parser("run", help="Run a persistent paper-trading session.")
    run.add_argument("--quote-file", type=Path, help="JSON quote feed path.")
    run.add_argument("--poll-seconds", type=float, help="Override configured polling interval.")
    run.add_argument("--max-iterations", type=int, help="Stop after N polling iterations.")
    run.add_argument(
        "--no-collect",
        action="store_true",
        help="Read existing quote cache only; do not fetch fresh quotes.",
    )
    run.add_argument(
        "--quiet",
        action="store_true",
        help="Disable countdown progress while waiting for the next poll.",
    )
    _add_common_args(run)
    return parser


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--symbols-config",
        type=Path,
        default=Path(__file__).parent / "config" / "symbols.cfg",
        help="Path to allowed symbols config.",
    )
    parser.add_argument(
        "--personal-config",
        type=Path,
        help="Path to personal account config. Defaults to SERVICE_ROOT/rh_agentic.json.",
    )
    parser.add_argument(
        "--journal",
        type=Path,
        help="Path to append decision JSONL. Overrides personal config when set.",
    )


def main() -> int:
    args = build_parser().parse_args()
    if args.command is None:
        raise SystemExit("Specify a command: analyze or run")

    personal_config = args.personal_config or get_personal_config_path()
    config = load_config(args.symbols_config, personal_config)
    if getattr(args, "poll_seconds", None):
        config = replace(config, poll_seconds=args.poll_seconds)

    bot = AgenticBot(config=config)
    if args.journal:
        bot.journal.path = args.journal

    if args.command == "run":
        quote_path = args.quote_file or config.quote_source_path
        if not quote_path:
            raise SystemExit("run requires --quote-file or quote_source_path in personal config")
        collector = None
        if not args.no_collect:
            collector = QuoteCollector(
                source=YahooChartMarketDataSource(),
                cache_path=quote_path,
            )
        session = PaperSession(
            config=config,
            quote_provider=JsonQuoteProvider(quote_path),
            quote_collector=collector,
            bot=bot,
            show_progress=not args.quiet,
        )
        result = session.run(max_iterations=args.max_iterations)
        print(
            "[summary] "
            f"iterations={result.iterations} decisions={result.decisions} "
            f"skipped_quotes={result.skipped_quotes} collection_errors={result.collection_errors} "
            f"paper_cash=${result.paper_cash:.2f} interrupted={result.interrupted}"
        )
        if result.positions:
            open_positions = {
                symbol: quantity
                for symbol, quantity in result.positions.items()
                if quantity > 0
            }
            print(f"[summary] paper_positions={open_positions}")
        return 0

    if args.command == "backtest":
        symbols = tuple(symbol.upper() for symbol in (args.symbol or config.symbols.stocks))
        if not symbols:
            raise SystemExit("backtest requires --symbol or configured stock symbols")

        source = YahooDailyCandleSource()
        risk_overrides = {
            "min_order_dollars": (
                args.min_order_dollars
                if args.min_order_dollars is not None
                else config.risk.min_order_dollars
            ),
            "max_trade_dollars": (
                args.max_trade_dollars
                if args.max_trade_dollars is not None
                else config.risk.max_trade_dollars
            ),
            "min_cash_reserve": (
                args.min_cash_reserve
                if args.min_cash_reserve is not None
                else config.risk.min_cash_reserve
            ),
        }
        if args.portfolio:
            candles_by_symbol = {
                symbol: source.get_daily_candles(symbol, range_=args.range)
                for symbol in symbols
            }
            result = run_daily_trend_portfolio_backtest(
                candles_by_symbol,
                starting_cash=args.starting_cash,
                target_dollars=args.target_dollars,
                slippage_pct=args.slippage_pct,
                max_open_positions=(
                    args.max_open_positions
                    if args.max_open_positions is not None
                    else config.risk.max_open_positions
                ),
                max_new_buys_per_day=(
                    args.max_new_buys_per_day
                    if args.max_new_buys_per_day is not None
                    else config.risk.max_new_buys_per_day
                ),
                max_daily_trades=(
                    args.max_daily_trades
                    if args.max_daily_trades is not None
                    else config.risk.max_daily_trades
                ),
                max_total_exposure_dollars=(
                    args.max_total_exposure_dollars
                    if args.max_total_exposure_dollars is not None
                    else config.risk.max_total_exposure_dollars
                ),
                **risk_overrides,
            )
            print(
                f"{result.symbol}: ending=${result.ending_value:.2f} "
                f"return={result.total_return_pct:.2f}% "
                f"buy_hold={result.buy_hold_return_pct:.2f}% "
                f"max_dd={result.max_drawdown_pct:.2f}% "
                f"trades={len(result.trades)}"
            )
            return 0

        for symbol in symbols:
            candles = source.get_daily_candles(symbol, range_=args.range)
            result = run_daily_trend_backtest(
                symbol,
                candles,
                starting_cash=args.starting_cash,
                target_dollars=args.target_dollars,
                slippage_pct=args.slippage_pct,
                **risk_overrides,
            )
            print(
                f"{result.symbol}: ending=${result.ending_value:.2f} "
                f"return={result.total_return_pct:.2f}% "
                f"buy_hold={result.buy_hold_return_pct:.2f}% "
                f"max_dd={result.max_drawdown_pct:.2f}% "
                f"trades={len(result.trades)}"
            )
        return 0

    if args.command == "mcp-check":
        if not config.account_number:
            raise SystemExit("mcp-check requires account_number in personal config")
        client = StreamableHttpMcpToolClient(
            config.mcp_url,
            bearer_token_env_var=config.mcp_bearer_token_env_var or None,
        )
        broker = AgenticMcpEquityBroker(
            account_number=config.account_number,
            client=client,
            live_trading_enabled=False,
            auto_place_orders=False,
        )
        snapshot = broker.get_account_snapshot()
        intent = broker.review_order(_mcp_check_intent(args.symbol), price=100.0)
        print(
            f"account_cash=${snapshot.cash:.2f} "
            f"positions={len(snapshot.positions)} "
            f"review_approved={intent.approved} "
            f"review_reason={intent.reason}"
        )
        if intent.alerts:
            print(f"review_alerts={list(intent.alerts)}")
        return 0

    quote = ManualQuoteProvider(args.price, args.previous_close).get_quote(args.symbol.strip().upper())
    entry = bot.analyze(quote)

    decision = entry.decision
    risk = entry.risk
    print(f"{decision['symbol']}: {decision['action']}")
    print(f"Reason: {decision['reason']}")
    print(f"Risk: {risk['reason']}")
    print("No order submitted: dry-run mode")
    return 0


def _mcp_check_intent(symbol: str) -> OrderIntent:
    return OrderIntent(symbol=symbol, side="buy", dollar_amount=1.0)


if __name__ == "__main__":
    raise SystemExit(main())
