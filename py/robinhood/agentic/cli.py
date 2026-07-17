"""Command-line entry point for the agentic dry-run bot."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from datetime import datetime
from datetime import time as datetime_time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .backtest import run_daily_trend_backtest, run_daily_trend_portfolio_backtest
from .bot import AgenticBot
from .broker import AccountSnapshot, OrderIntent, OrderResult, OrderReview
from .config import LIVE_ORDER_CONFIRMATION, AgenticConfig, get_personal_config_path, load_config
from .daemon import PersistentDaemon
from .daemon_state import (
    DaemonLease,
    DaemonState,
    DaemonStateStore,
    PendingOrderState,
    clear_pending_orders,
    daemon_state_summary,
    replace_state_pending,
    reset_trade_day_after_unresolved_order,
)
from .journal import DecisionJournal
from .market_clock import MarketCalendar, MarketClock
from .market_data import (
    CandleCollector,
    QuoteCollector,
    ValidatedHistoricalMarketDataSource,
    YahooChartMarketDataSource,
    YahooDailyCandleSource,
)
from .mcp_broker import AgenticMcpEquityBroker
from .mcp_client import StreamableHttpMcpToolClient
from .quotes import JsonQuoteProvider, ManualQuoteProvider
from .session import BrokerSession, DailyCandleBrokerSession, PaperSession, SessionResult, _execution_payload


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
    mcp_check.add_argument("--asset-class", choices=("equity", "crypto"), default="equity")
    _add_common_args(mcp_check)

    mcp_review = subparsers.add_parser("mcp-review", help="Review an MCP equity or crypto order without placing it.")
    mcp_review.add_argument("--symbol", default="SPY", help="Symbol to review.")
    mcp_review.add_argument("--dollars", type=float, default=1.0, help="Dollar amount for buy review.")
    mcp_review.add_argument("--asset-class", choices=("equity", "crypto"), default="equity")
    _add_common_args(mcp_review)

    live_check = subparsers.add_parser("live-check", help="Check live-placement readiness without placing orders.")
    live_check.add_argument("--symbol", default="SPY", help="Symbol to review for readiness.")
    live_check.add_argument("--dollars", type=float, default=1.0, help="Dollar amount for readiness review.")
    live_check.add_argument("--asset-class", choices=("equity", "crypto"), default="equity")
    _add_common_args(live_check)

    mcp_place_once = subparsers.add_parser("mcp-place-once", help="Place one live MCP equity or crypto order.")
    mcp_place_once.add_argument("--symbol", required=True, help="Symbol to buy.")
    mcp_place_once.add_argument("--dollars", type=float, required=True, help="Dollar amount to buy.")
    mcp_place_once.add_argument("--asset-class", choices=("equity", "crypto"), default="equity")
    _add_common_args(mcp_place_once)

    mcp_login = subparsers.add_parser("mcp-login", help="Authorize the standalone Agentic MCP client.")
    _add_common_args(mcp_login)

    mcp_tools = subparsers.add_parser("mcp-tools", help="List available Agentic MCP tools.")
    mcp_tools.add_argument("--filter", help="Only print tools whose name contains this text.")
    mcp_tools.add_argument("--json", action="store_true", help="Print full tool metadata as JSON.")
    _add_common_args(mcp_tools)

    mcp_orders = subparsers.add_parser("mcp-orders", help="Fetch equity order status from MCP.")
    mcp_orders.add_argument("--symbol", help="Filter to one symbol.")
    mcp_orders.add_argument("--state", help="Filter to one order state.")
    mcp_orders.add_argument("--order-id", help="Fetch one order by broker order id.")
    mcp_orders.add_argument("--created-at-gte", help="Filter to orders created at or after this UTC time/date.")
    mcp_orders.add_argument("--placed-agent", help="Filter by source, e.g. agentic.")
    mcp_orders.add_argument("--limit", type=int, default=10, help="Maximum summarized orders to print.")
    mcp_orders.add_argument("--json", action="store_true", help="Print raw order payload as JSON.")
    _add_common_args(mcp_orders)

    mcp_reconcile = subparsers.add_parser(
        "mcp-reconcile-orders",
        help="Append read-only order reconciliation events for broker journal rows.",
    )
    mcp_reconcile.add_argument("--symbol", help="Only reconcile one symbol.")
    mcp_reconcile.add_argument("--limit", type=int, default=20, help="Maximum journal executions to scan.")
    mcp_reconcile.add_argument("--dry-run", action="store_true", help="Print matches without appending events.")
    _add_common_args(mcp_reconcile)

    market_clock = subparsers.add_parser("market-clock", help="Print current market-clock state.")
    market_clock.add_argument("--timezone", default="America/New_York", help="Market timezone.")
    _add_common_args(market_clock)

    daemon_state = subparsers.add_parser("daemon-state", help="Print persistent daemon state.")
    daemon_state.add_argument("--state-file", type=Path, help="Daemon state JSON path.")
    daemon_state.add_argument("--json", action="store_true", help="Print raw daemon state JSON.")
    _add_common_args(daemon_state)

    daemon_reconcile = subparsers.add_parser(
        "daemon-reconcile",
        help="Reconcile pending daemon state orders against broker readback.",
    )
    daemon_reconcile.add_argument("--state-file", type=Path, help="Daemon state JSON path.")
    daemon_reconcile.add_argument("--dry-run", action="store_true", help="Print reconciliation without saving state.")
    _add_common_args(daemon_reconcile)

    daemon_clear = subparsers.add_parser(
        "daemon-clear-pending",
        help="Clear pending daemon orders with an explicit operator reason.",
    )
    daemon_clear.add_argument("--state-file", type=Path, help="Daemon state JSON path.")
    daemon_clear.add_argument("--reason", required=True, help="Operator reason for clearing pending state.")
    _add_common_args(daemon_clear)

    daemon_reset = subparsers.add_parser(
        "daemon-reset-trade-day",
        help="Reset today's daemon trading state after operator-confirmed no broker order exists.",
    )
    daemon_reset.add_argument("--state-file", type=Path, help="Daemon state JSON path.")
    daemon_reset.add_argument("--reason", required=True, help="Operator reason for resetting daemon state.")
    _add_common_args(daemon_reset)

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

    run_daily = subparsers.add_parser(
        "run-daily",
        help="Run one daily-candle broker pass for daily trend lanes.",
    )
    run_daily.add_argument("--candle-file", type=Path, required=True, help="JSON daily candle cache path.")
    run_daily.add_argument("--range", default="1y", help="Yahoo chart range for daily candles.")
    run_daily.add_argument(
        "--review-only",
        action="store_true",
        help="Force broker review mode for this run, even when live gates are enabled.",
    )
    run_daily.add_argument(
        "--what-if-max-open-positions",
        type=int,
        help="Review-only override for risk.max_open_positions.",
    )
    run_daily.add_argument(
        "--what-if-max-total-exposure-dollars",
        type=float,
        help="Review-only override for risk.max_total_exposure_dollars.",
    )
    _add_common_args(run_daily)

    run_daily_daemon = subparsers.add_parser(
        "run-daily-daemon",
        help="Run daily-candle broker passes once per trading day.",
    )
    run_daily_daemon.add_argument("--candle-file", type=Path, required=True, help="JSON daily candle cache path.")
    run_daily_daemon.add_argument("--range", default="1y", help="Yahoo chart range for daily candles.")
    run_daily_daemon.add_argument(
        "--review-only",
        action="store_true",
        help="Force broker review mode for this daemon, even when live gates are enabled.",
    )
    run_daily_daemon.add_argument("--run-at", default="09:35", help="Local market time to run each day, HH:MM.")
    run_daily_daemon.add_argument("--timezone", default="America/New_York", help="Timezone for --run-at.")
    run_daily_daemon.add_argument("--poll-seconds", type=float, default=60.0, help="Seconds to sleep while waiting.")
    run_daily_daemon.add_argument("--max-iterations", type=int, help="Stop after N daily passes.")
    run_daily_daemon.add_argument(
        "--rerun-today",
        action="store_true",
        help="Ignore today's existing daily_daemon_pass marker and run today once more.",
    )
    run_daily_daemon.add_argument(
        "--max-live-order-dollars",
        type=float,
        default=5.0,
        help="Maximum order dollars for daemon-planned live/review orders.",
    )
    _add_common_args(run_daily_daemon)

    run_daemon = subparsers.add_parser(
        "run-daemon",
        help="Run the persistent market-aware trading daemon.",
    )
    run_daemon.add_argument("--candle-file", type=Path, required=True, help="JSON daily candle cache path.")
    run_daemon.add_argument("--range", default="1y", help="Yahoo chart range for daily candles.")
    run_daemon.add_argument("--review-only", action="store_true", help="Force review mode even when live gates are on.")
    run_daemon.add_argument("--max-iterations", type=int, help="Stop after N daemon loop iterations.")
    run_daemon.add_argument("--status-only", action="store_true", help="Print daemon clock/state status and exit.")
    run_daemon.add_argument(
        "--exit-when-done",
        action="store_true",
        help="Exit once today's lanes are complete or live trading capacity is exhausted.",
    )
    run_daemon.add_argument("--state-file", type=Path, help="Daemon state JSON path.")
    run_daemon.add_argument("--lease-file", type=Path, help="Exclusive daemon lease path (defaults beside state).")
    run_daemon.add_argument(
        "--max-live-order-dollars",
        type=float,
        default=5.0,
        help="Maximum order dollars for daemon-planned live/review orders.",
    )
    _add_common_args(run_daemon)
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
        quote_provider = JsonQuoteProvider(quote_path)
        broker_name = config.broker.strip().lower()
        if broker_name == "agentic_mcp":
            if not config.account_number:
                raise SystemExit("run with agentic_mcp broker requires account_number in personal config")
            broker = AgenticMcpEquityBroker(
                account_number=config.account_number,
                client=_build_mcp_client(config),
                live_trading_enabled=_live_order_gates_enabled(config),
                auto_place_orders=config.auto_place_orders,
                max_live_order_dollars=config.risk.max_trade_dollars,
            )
            session = BrokerSession(
                config=config,
                quote_provider=quote_provider,
                quote_collector=collector,
                bot=bot,
                broker=broker,
                show_progress=not args.quiet,
            )
            summary_cash_label = "account_cash"
        else:
            session = PaperSession(
                config=config,
                quote_provider=quote_provider,
                quote_collector=collector,
                bot=bot,
                show_progress=not args.quiet,
            )
            summary_cash_label = "paper_cash"
        result = session.run(max_iterations=args.max_iterations)
        print(
            "[summary] "
            f"iterations={result.iterations} decisions={result.decisions} "
            f"skipped_quotes={result.skipped_quotes} collection_errors={result.collection_errors} "
            f"{summary_cash_label}=${result.paper_cash:.2f} interrupted={result.interrupted}"
        )
        if result.positions:
            open_positions = {symbol: quantity for symbol, quantity in result.positions.items() if quantity > 0}
            print(f"[summary] paper_positions={open_positions}")
        return 0

    if args.command == "market-clock":
        clock = _market_clock(config, timezone=args.timezone)
        status = clock.status()
        print(
            "[market-clock] "
            f"state={status.state} trade_day={status.trade_day or '-'} "
            f"trading_allowed={status.trading_allowed} warmup_allowed={status.warmup_allowed} "
            f"now={status.now.isoformat()} next_wakeup={status.next_wakeup.isoformat()} "
            f"next_open={status.next_open.isoformat()} next_close={status.next_close.isoformat()}"
        )
        return 0

    if args.command == "daemon-state":
        state_path = _daemon_state_path(config, args.state_file)
        state = DaemonStateStore(state_path).load()
        if args.json:
            print(json.dumps(_daemon_state_json_payload(state), indent=2, sort_keys=True))
        else:
            print(daemon_state_summary(state, state_path))
        return 0

    if args.command == "daemon-reconcile":
        if not config.account_number:
            raise SystemExit("daemon-reconcile requires account_number in personal config")
        state_path = _daemon_state_path(config, args.state_file)
        store = DaemonStateStore(state_path)
        client = _build_mcp_client(config)
        result = _reconcile_daemon_state(config.account_number, client, store.load())
        print(
            "[daemon-reconcile] "
            f"checked={result['checked']} matched={result['matched']} "
            f"remaining_pending={len(result['state'].pending_orders)} dry_run={args.dry_run}"
        )
        for line in result["lines"]:
            print(line)
        if not args.dry_run:
            store.save(result["state"])
            DecisionJournal(Path(config.journal_path)).append_event(
                {
                    "event_type": "daemon_state_reconciliation",
                    "source": "daemon-reconcile",
                    "checked": result["checked"],
                    "matched": result["matched"],
                    "remaining_pending": len(result["state"].pending_orders),
                }
            )
        return 0

    if args.command == "daemon-clear-pending":
        reason = args.reason.strip()
        if not reason:
            raise SystemExit("--reason must not be empty")
        state_path = _daemon_state_path(config, args.state_file)
        store = DaemonStateStore(state_path)
        state = store.load()
        cleared = len(state.pending_orders)
        updated = clear_pending_orders(state)
        store.save(updated)
        DecisionJournal(Path(config.journal_path)).append_event(
            {
                "event_type": "daemon_pending_clear",
                "source": "daemon-clear-pending",
                "reason": reason,
                "cleared_pending_orders": cleared,
                "pending_orders": [_pending_order_payload(order) for order in state.pending_orders],
            }
        )
        print(f"[daemon-clear-pending] cleared={cleared} reason={reason}")
        return 0

    if args.command == "daemon-reset-trade-day":
        reason = args.reason.strip()
        if not reason:
            raise SystemExit("--reason must not be empty")
        state_path = _daemon_state_path(config, args.state_file)
        store = DaemonStateStore(state_path)
        state = store.load()
        updated = reset_trade_day_after_unresolved_order(state)
        store.save(updated)
        DecisionJournal(Path(config.journal_path)).append_event(
            {
                "event_type": "daemon_trade_day_reset",
                "source": "daemon-reset-trade-day",
                "reason": reason,
                "trading_day": state.trading_day,
                "previous_live_order_attempts": state.live_order_attempts,
                "previous_live_orders_submitted": state.live_orders_submitted,
                "previous_live_notional_attempted": state.live_notional_attempted,
                "previous_live_notional_submitted": state.live_notional_submitted,
                "previous_lane_evaluations": dict(state.lane_evaluations),
                "previous_pending_orders": [_pending_order_payload(order) for order in state.pending_orders],
            }
        )
        print(
            "[daemon-reset-trade-day] "
            f"trading_day={state.trading_day or '-'} "
            f"cleared_pending={len(state.pending_orders)} "
            f"reset_attempts={state.live_order_attempts} reason={reason}"
        )
        return 0

    if args.command == "run-daemon":
        broker_name = config.broker.strip().lower()
        if broker_name != "agentic_mcp":
            raise SystemExit("run-daemon requires broker=agentic_mcp in personal config")
        if not config.account_number:
            raise SystemExit("run-daemon with agentic_mcp broker requires account_number in personal config")
        if args.max_live_order_dollars <= 0:
            raise SystemExit("--max-live-order-dollars must be greater than 0")
        if config.risk.max_live_order_attempts_per_day <= 0:
            raise SystemExit("risk.max_live_order_attempts_per_day must be greater than 0")

        daemon_config = replace(config, journal_path=str(args.journal)) if args.journal else config
        client = _build_mcp_client(config)

        def broker_factory(max_live_orders_per_process: int) -> AgenticMcpEquityBroker:
            return AgenticMcpEquityBroker(
                account_number=daemon_config.account_number,
                client=client,
                live_trading_enabled=_run_daily_live_trading_enabled(daemon_config, args.review_only),
                auto_place_orders=_run_daily_auto_place_orders(daemon_config, args.review_only),
                max_live_order_dollars=args.max_live_order_dollars,
                max_live_orders_per_process=max_live_orders_per_process,
            )

        state_path = _daemon_state_path(daemon_config, args.state_file)
        daemon = PersistentDaemon(
            config=daemon_config,
            state_store=DaemonStateStore(state_path),
            broker_factory=broker_factory,
            candle_file=args.candle_file,
            candle_range=args.range,
            clock=_market_clock(daemon_config),
            review_only=args.review_only,
            max_live_order_dollars=args.max_live_order_dollars,
            order_result_reconciler=lambda result: _reconcile_order_result(
                daemon_config.account_number,
                client,
                result,
            ),
            state_reconciler=lambda state: _reconcile_daemon_state(
                daemon_config.account_number,
                client,
                state,
            )["state"],
        )
        lease_path = args.lease_file or state_path.with_suffix(".lease.json")
        with DaemonLease(lease_path):
            result = daemon.run(
                max_iterations=args.max_iterations,
                status_only=args.status_only,
                exit_when_done=args.exit_when_done,
            )
        print(
            "[summary] "
            f"iterations={result.iterations} decisions={result.decisions} "
            f"skipped_candles={result.skipped_quotes} collection_errors={result.collection_errors} "
            f"account_cash=${result.paper_cash:.2f}"
        )
        return 0

    if args.command == "run-daily":
        broker_name = config.broker.strip().lower()
        if broker_name != "agentic_mcp":
            raise SystemExit("run-daily requires broker=agentic_mcp in personal config")
        if not config.account_number:
            raise SystemExit("run-daily with agentic_mcp broker requires account_number in personal config")
        config = _apply_run_daily_what_if_overrides(config, args)
        bot = AgenticBot(config=config)
        if args.journal:
            bot.journal.path = args.journal
        if args.what_if_max_open_positions is not None:
            print(f"[what-if] max_open_positions={config.risk.max_open_positions}")
        if args.what_if_max_total_exposure_dollars is not None:
            print(f"[what-if] max_total_exposure_dollars={config.risk.max_total_exposure_dollars:.2f}")

        broker = AgenticMcpEquityBroker(
            account_number=config.account_number,
            client=_build_mcp_client(config),
            live_trading_enabled=_run_daily_live_trading_enabled(config, args.review_only),
            auto_place_orders=_run_daily_auto_place_orders(config, args.review_only),
            max_live_order_dollars=config.risk.max_trade_dollars,
        )
        session = DailyCandleBrokerSession(
            config=config,
            candle_collector=CandleCollector(
                ValidatedHistoricalMarketDataSource(YahooDailyCandleSource()), args.candle_file
            ),
            broker=broker,
            bot=bot,
            candle_range=args.range,
        )
        result = session.run_once()
        print(
            "[summary] "
            f"iterations={result.iterations} decisions={result.decisions} "
            f"skipped_candles={result.skipped_quotes} collection_errors={result.collection_errors} "
            f"account_cash=${result.paper_cash:.2f}"
        )
        if result.positions:
            open_positions = {symbol: quantity for symbol, quantity in result.positions.items() if quantity > 0}
            print(f"[summary] positions={open_positions}")
        return 0

    if args.command == "run-daily-daemon":
        broker_name = config.broker.strip().lower()
        if broker_name != "agentic_mcp":
            raise SystemExit("run-daily-daemon requires broker=agentic_mcp in personal config")
        if not config.account_number:
            raise SystemExit("run-daily-daemon with agentic_mcp broker requires account_number in personal config")
        if args.max_live_order_dollars <= 0:
            raise SystemExit("--max-live-order-dollars must be greater than 0")
        if args.poll_seconds <= 0:
            raise SystemExit("--poll-seconds must be greater than 0")

        run_time = _parse_daily_daemon_run_time(args.run_at)
        tz = _daily_daemon_timezone(args.timezone)
        effective_journal_path = args.journal or config.journal_path
        completed_days = _daily_daemon_completed_days(effective_journal_path)
        if args.rerun_today:
            current_trade_day = _daily_daemon_trade_day(datetime.now(tz))
            if current_trade_day:
                completed_days.discard(current_trade_day)
                print(f"[daemon] rerun_today=true ignoring completed marker for {current_trade_day}")
        passes = 0
        print(
            "[daemon] "
            f"run_at={args.run_at} timezone={args.timezone} "
            f"review_only={args.review_only} max_live_order_dollars=${args.max_live_order_dollars:.2f}"
        )
        while args.max_iterations is None or passes < args.max_iterations:
            now = datetime.now(tz)
            trade_day = _daily_daemon_trade_day(now)
            if trade_day and _daily_daemon_due(now, run_time, completed_days):
                effective_config = _run_daily_daemon_config(config, args.max_live_order_dollars)
                bot = AgenticBot(config=effective_config)
                if args.journal:
                    bot.journal.path = args.journal
                client = _build_mcp_client(effective_config)
                broker = AgenticMcpEquityBroker(
                    account_number=effective_config.account_number,
                    client=client,
                    live_trading_enabled=_run_daily_live_trading_enabled(effective_config, args.review_only),
                    auto_place_orders=_run_daily_auto_place_orders(effective_config, args.review_only),
                    max_live_order_dollars=args.max_live_order_dollars,
                )
                session = DailyCandleBrokerSession(
                    config=effective_config,
                    candle_collector=CandleCollector(
                        ValidatedHistoricalMarketDataSource(YahooDailyCandleSource()), args.candle_file
                    ),
                    broker=broker,
                    bot=bot,
                    candle_range=args.range,
                    order_result_reconciler=(
                        lambda result, account_number=effective_config.account_number, mcp_client=client: (
                            _reconcile_order_result(account_number, mcp_client, result)
                        )
                    ),
                )
                result = session.run_once()
                completed_days.add(trade_day)
                _append_daily_daemon_completion(bot.journal, trade_day, result, args.review_only)
                passes += 1
                print(
                    "[daemon-summary] "
                    f"trade_day={trade_day} passes={passes} decisions={result.decisions} "
                    f"skipped_candles={result.skipped_quotes} collection_errors={result.collection_errors} "
                    f"account_cash=${result.paper_cash:.2f}"
                )
                continue

            if args.max_iterations is not None and passes >= args.max_iterations:
                break
            wait = min(args.poll_seconds, _daily_daemon_seconds_until_next_check(now, run_time))
            print(f"[daemon] waiting {wait:.1f}s for next daily run check")
            time.sleep(wait)
        return 0

    if args.command == "backtest":
        symbols = tuple(symbol.upper() for symbol in (args.symbol or config.symbols.stocks))
        if not symbols:
            raise SystemExit("backtest requires --symbol or configured stock symbols")

        source = YahooDailyCandleSource()
        risk_overrides = {
            "min_order_dollars": (
                args.min_order_dollars if args.min_order_dollars is not None else config.risk.min_order_dollars
            ),
            "max_trade_dollars": (
                args.max_trade_dollars if args.max_trade_dollars is not None else config.risk.max_trade_dollars
            ),
            "min_cash_reserve": (
                args.min_cash_reserve if args.min_cash_reserve is not None else config.risk.min_cash_reserve
            ),
        }
        if args.portfolio:
            candles_by_symbol = {symbol: source.get_daily_candles(symbol, range_=args.range) for symbol in symbols}
            result = run_daily_trend_portfolio_backtest(
                candles_by_symbol,
                starting_cash=args.starting_cash,
                target_dollars=args.target_dollars,
                slippage_pct=args.slippage_pct,
                max_open_positions=(
                    args.max_open_positions if args.max_open_positions is not None else config.risk.max_open_positions
                ),
                max_new_buys_per_day=(
                    args.max_new_buys_per_day
                    if args.max_new_buys_per_day is not None
                    else config.risk.max_new_buys_per_day
                ),
                max_daily_trades=(
                    args.max_daily_trades if args.max_daily_trades is not None else config.risk.max_daily_trades
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
        broker = _build_review_only_mcp_broker(config)
        snapshot = broker.get_account_snapshot()
        intent = broker.review_order(_mcp_check_intent(args.symbol, args.asset_class), price=100.0)
        print(
            f"account_cash=${snapshot.cash:.2f} "
            f"positions={len(snapshot.positions)} "
            f"review_approved={intent.approved} "
            f"review_reason={intent.reason}"
        )
        if intent.alerts:
            print(f"review_alerts={list(intent.alerts)}")
        return 0

    if args.command == "mcp-review":
        if not config.account_number:
            raise SystemExit("mcp-review requires account_number in personal config")
        intent = _mcp_review_intent(args.symbol, args.dollars, args.asset_class)
        broker = _build_review_only_mcp_broker(config)
        snapshot = broker.get_account_snapshot()
        review = broker.review_order(intent, price=100.0)
        print(
            f"account_cash=${snapshot.cash:.2f} "
            f"positions={len(snapshot.positions)} "
            f"symbol={intent.symbol} "
            f"asset_class={intent.asset_class} "
            f"side={intent.side} "
            f"dollars=${intent.dollar_amount:.2f} "
            f"review_approved={review.approved} "
            f"review_reason={review.reason}"
        )
        if review.estimated_quantity is not None:
            print(f"estimated_quantity={review.estimated_quantity:.6f}")
        if review.estimated_cost is not None:
            print(f"estimated_cost=${review.estimated_cost:.2f}")
        if review.alerts:
            print(f"review_alerts={list(review.alerts)}")
        print("No order submitted: mcp-review is review-only")
        return 0

    if args.command == "live-check":
        if not config.account_number:
            raise SystemExit("live-check requires account_number in personal config")
        intent = _mcp_review_intent(args.symbol, args.dollars, args.asset_class)
        broker = _build_review_only_mcp_broker(config)
        snapshot = broker.get_account_snapshot()
        review = broker.review_order(intent, price=100.0)
        failures = _live_readiness_failures(config, snapshot, review, intent)
        print(
            f"readiness={'PASS' if not failures else 'FAIL'} "
            f"account_cash=${snapshot.cash:.2f} "
            f"positions={len(snapshot.positions)} "
            f"symbol={intent.symbol} "
            f"asset_class={intent.asset_class} "
            f"dollars=${intent.dollar_amount:.2f} "
            f"review_approved={review.approved}"
        )
        if review.alerts:
            print(f"review_alerts={list(review.alerts)}")
        if failures:
            for failure in failures:
                print(f"FAIL: {failure}")
            print("No order submitted: live-check is readiness-only")
            return 1
        print("No order submitted: live-check is readiness-only")
        return 0

    if args.command == "mcp-place-once":
        if not config.account_number:
            raise SystemExit("mcp-place-once requires account_number in personal config")
        intent = _mcp_review_intent(args.symbol, args.dollars, args.asset_class)
        review_broker = _build_review_only_mcp_broker(config)
        snapshot = review_broker.get_account_snapshot()
        review = review_broker.review_order(intent, price=100.0)
        failures = _live_readiness_failures(config, snapshot, review, intent)
        if failures:
            print(
                f"readiness=FAIL account_cash=${snapshot.cash:.2f} "
                f"positions={len(snapshot.positions)} symbol={intent.symbol} "
                f"asset_class={intent.asset_class} "
                f"dollars=${intent.dollar_amount:.2f} review_approved={review.approved}"
            )
            for failure in failures:
                print(f"FAIL: {failure}")
            print("No order submitted: mcp-place-once readiness failed")
            return 1

        client = _build_mcp_client(config)
        broker = AgenticMcpEquityBroker(
            account_number=config.account_number,
            client=client,
            live_trading_enabled=_live_order_gates_enabled(config),
            auto_place_orders=config.auto_place_orders,
            max_live_order_dollars=config.risk.max_trade_dollars,
        )
        result = broker.place_order(intent, price=100.0)
        result = _reconcile_order_result(config.account_number, client, result)
        _journal_place_once(config, result)
        print(
            f"order_status={result.status} placed={result.placed} "
            f"symbol={intent.symbol} asset_class={intent.asset_class} dollars=${intent.dollar_amount:.2f} "
            f"reason={result.reason}"
        )
        if result.order_id:
            print(f"order_id={result.order_id}")
        return 0 if result.placed else 1

    if args.command == "mcp-login":
        client = _build_mcp_client(config)
        payload = client.call_tool("get_accounts", {})
        token_path = _mcp_token_store_path(config)
        print(f"mcp_login_complete token_store={token_path}")
        if isinstance(payload, dict):
            results = payload.get("results")
            if isinstance(results, list):
                print(f"accounts={len(results)}")
        return 0

    if args.command == "mcp-tools":
        client = _build_mcp_client(config)
        tools = client.list_tools()
        if args.filter:
            needle = args.filter.strip().lower()
            tools = [tool for tool in tools if needle in str(tool.get("name", "")).lower()]
        if args.json:
            print(json.dumps(tools, indent=2, sort_keys=True))
        else:
            for tool in tools:
                description = tool.get("description") or ""
                _print_console_safe(f"{tool.get('name', '')}: {description}".rstrip())
        return 0

    if args.command == "mcp-orders":
        if not config.account_number:
            raise SystemExit("mcp-orders requires account_number in personal config")
        client = _build_mcp_client(config)
        arguments = _mcp_orders_arguments(config.account_number, args)
        payload = client.call_tool("get_equity_orders", arguments)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        orders = _extract_order_rows(payload)
        limit = max(0, args.limit)
        print(f"orders={len(orders)}")
        for order in orders[:limit]:
            _print_console_safe(_format_order_row(order))
        if len(orders) > limit:
            print(f"... {len(orders) - limit} more orders omitted; rerun with --limit {len(orders)} or --json")
        return 0

    if args.command == "mcp-reconcile-orders":
        if not config.account_number:
            raise SystemExit("mcp-reconcile-orders requires account_number in personal config")
        client = _build_mcp_client(config)
        rows = _read_journal_rows(config.journal_path)
        events = _reconcile_journal_rows(
            account_number=config.account_number,
            client=client,
            rows=rows,
            symbol=args.symbol,
            limit=args.limit,
        )
        print(f"reconciled={len(events)} dry_run={args.dry_run}")
        for event in events:
            order = event.get("order", {})
            _print_console_safe(_format_order_row(order) if isinstance(order, dict) else str(order))
        if not args.dry_run:
            journal = DecisionJournal(Path(config.journal_path))
            for event in events:
                journal.append_event(event)
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


def _mcp_check_intent(symbol: str, asset_class: str = "equity") -> OrderIntent:
    return OrderIntent(symbol=symbol, side="buy", asset_class=asset_class, dollar_amount=1.0)


def _mcp_review_intent(symbol: str, dollars: float, asset_class: str = "equity") -> OrderIntent:
    if dollars <= 0:
        raise SystemExit("mcp-review requires --dollars greater than 0")
    return OrderIntent(symbol=symbol, side="buy", asset_class=asset_class, dollar_amount=round(dollars, 2))


def _build_review_only_mcp_broker(config) -> AgenticMcpEquityBroker:
    return AgenticMcpEquityBroker(
        account_number=config.account_number,
        client=_build_mcp_client(config),
        live_trading_enabled=False,
        auto_place_orders=False,
    )


def _journal_place_once(config: AgenticConfig, result) -> None:
    journal = DecisionJournal(Path(config.journal_path))
    execution = _execution_payload(result)
    if isinstance(result.raw, dict) and isinstance(result.raw.get("reconciled_order"), dict):
        execution["reconciliation"] = _order_status_payload(result.raw["reconciled_order"])
    journal.append_event(
        {
            "event_type": "broker_execution",
            "source": "mcp-place-once",
            "dry_run": config.dry_run,
            "symbol": result.intent.symbol,
            "action": result.intent.side.upper(),
            "execution": execution,
        }
    )


def _live_readiness_failures(
    config: AgenticConfig,
    snapshot: AccountSnapshot,
    review: OrderReview,
    intent: OrderIntent,
) -> list[str]:
    failures: list[str] = []
    broker_name = config.broker.strip().lower()
    risk = config.risk

    if broker_name != "agentic_mcp":
        failures.append("broker must be agentic_mcp")
    if config.dry_run:
        failures.append("dry_run must be false")
    if not config.live_trading_enabled:
        failures.append("live_trading_enabled must be true")
    if not config.auto_place_orders:
        failures.append("auto_place_orders must be true")
    if config.live_order_confirm != LIVE_ORDER_CONFIRMATION:
        failures.append("live_order_confirm must match required confirmation phrase")

    allowed_symbols = set(config.symbols.stocks) | set(config.symbols.crypto)
    if not allowed_symbols:
        failures.append("at least one allowed symbol is required")
    if intent.symbol not in allowed_symbols:
        failures.append(f"{intent.symbol} must be in allowed symbols")

    if risk.allow_shorts:
        failures.append("allow_shorts must be false")
    if risk.allow_options:
        failures.append("allow_options must be false")
    if risk.min_order_dollars <= 0:
        failures.append("min_order_dollars must be greater than 0")
    if risk.max_trade_dollars <= 0:
        failures.append("max_trade_dollars must be greater than 0")
    if risk.max_trade_dollars < risk.min_order_dollars:
        failures.append("max_trade_dollars must be at least min_order_dollars")
    if risk.max_daily_trades <= 0:
        failures.append("max_daily_trades must be greater than 0")
    if risk.max_new_buys_per_day <= 0:
        failures.append("max_new_buys_per_day must be greater than 0")
    if risk.max_open_positions <= 0:
        failures.append("max_open_positions must be greater than 0")
    if risk.max_total_exposure_dollars > 0 and risk.max_total_exposure_dollars < risk.min_order_dollars:
        failures.append("max_total_exposure_dollars must be 0 or at least min_order_dollars")

    if intent.dollar_amount is not None and intent.dollar_amount > risk.max_trade_dollars:
        failures.append("review dollars exceed max_trade_dollars")
    if intent.dollar_amount is not None and intent.dollar_amount < risk.min_order_dollars:
        failures.append("review dollars are below min_order_dollars")

    if snapshot.cash <= 0:
        failures.append("account cash must be greater than 0")
    if max(0.0, snapshot.cash - risk.min_cash_reserve) < risk.min_order_dollars:
        failures.append("cash available after min_cash_reserve is below min_order_dollars")

    if not review.approved:
        failures.append(f"MCP review must approve the readiness order: {review.reason}")
    if review.alerts:
        failures.append("MCP review returned alerts")
    return failures


def _live_order_gates_enabled(config: AgenticConfig) -> bool:
    return (
        not config.dry_run
        and config.live_trading_enabled
        and config.auto_place_orders
        and config.live_order_confirm == LIVE_ORDER_CONFIRMATION
    )


def _run_daily_live_trading_enabled(config: AgenticConfig, review_only: bool) -> bool:
    return False if review_only else _live_order_gates_enabled(config)


def _run_daily_auto_place_orders(config: AgenticConfig, review_only: bool) -> bool:
    return False if review_only else config.auto_place_orders


def _apply_run_daily_what_if_overrides(config: AgenticConfig, args) -> AgenticConfig:
    max_open_positions = getattr(args, "what_if_max_open_positions", None)
    max_total_exposure_dollars = getattr(args, "what_if_max_total_exposure_dollars", None)
    if max_open_positions is None and max_total_exposure_dollars is None:
        return config
    if not getattr(args, "review_only", False):
        raise SystemExit("run-daily what-if overrides require --review-only")
    if max_open_positions is not None and max_open_positions <= 0:
        raise SystemExit("--what-if-max-open-positions must be greater than 0")
    if max_total_exposure_dollars is not None and max_total_exposure_dollars < 0:
        raise SystemExit("--what-if-max-total-exposure-dollars must be 0 or greater")

    risk = config.risk
    if max_open_positions is not None:
        risk = replace(risk, max_open_positions=max_open_positions)
    if max_total_exposure_dollars is not None:
        risk = replace(risk, max_total_exposure_dollars=max_total_exposure_dollars)
    return replace(config, risk=risk)


def _run_daily_daemon_config(config: AgenticConfig, max_live_order_dollars: float) -> AgenticConfig:
    risk = replace(
        config.risk,
        max_trade_dollars=min(config.risk.max_trade_dollars, max_live_order_dollars),
    )
    return replace(config, risk=risk)


def _parse_daily_daemon_run_time(value: str) -> datetime_time:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (ValueError, AttributeError) as exc:
        raise SystemExit("--run-at must use HH:MM") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise SystemExit("--run-at must use HH:MM")
    return datetime_time(hour=hour, minute=minute)


def _daily_daemon_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise SystemExit(f"unknown timezone: {value}") from exc


def _daily_daemon_trade_day(now: datetime) -> str | None:
    if now.weekday() >= 5:
        return None
    return now.date().isoformat()


def _daily_daemon_due(now: datetime, run_time: datetime_time, completed_days: set[str]) -> bool:
    trade_day = _daily_daemon_trade_day(now)
    if trade_day is None or trade_day in completed_days:
        return False
    return now.time() >= run_time


def _daily_daemon_seconds_until_next_check(now: datetime, run_time: datetime_time) -> float:
    if now.weekday() >= 5 or now.time() >= run_time:
        return 60.0
    run_at = now.replace(hour=run_time.hour, minute=run_time.minute, second=0, microsecond=0)
    return max(1.0, (run_at - now).total_seconds())


def _daily_daemon_completed_days(journal_path: str | Path) -> set[str]:
    return {
        str(row["trade_day"])
        for row in _read_journal_rows(journal_path)
        if row.get("event_type") == "daily_daemon_pass" and row.get("trade_day")
    }


def _append_daily_daemon_completion(
    journal: DecisionJournal,
    trade_day: str,
    result: SessionResult,
    review_only: bool,
) -> None:
    journal.append_event(
        {
            "event_type": "daily_daemon_pass",
            "source": "run-daily-daemon",
            "trade_day": trade_day,
            "review_only": review_only,
            "decisions": result.decisions,
            "skipped_candles": result.skipped_quotes,
            "collection_errors": result.collection_errors,
            "account_cash": result.paper_cash,
        }
    )


def _build_mcp_client(config) -> StreamableHttpMcpToolClient:
    return StreamableHttpMcpToolClient(
        config.mcp_url,
        bearer_token_env_var=config.mcp_bearer_token_env_var or None,
        oauth_token_store_path=_mcp_token_store_path(config),
        oauth_callback_port=config.mcp_oauth_callback_port,
        oauth_scope=config.mcp_oauth_scope or None,
    )


def _mcp_token_store_path(config) -> Path:
    if config.mcp_token_store_path:
        return Path(config.mcp_token_store_path)
    service_root = os.environ.get("SERVICE_ROOT")
    if not service_root:
        raise RuntimeError("SERVICE_ROOT must be set for MCP token storage")
    return Path(service_root) / "rh_agentic_mcp_tokens.json"


def _market_clock(config: AgenticConfig, timezone: str = "America/New_York") -> MarketClock:
    return MarketClock(
        timezone=timezone,
        pre_open_warmup_minutes=config.pre_open_warmup_minutes,
        calendar=MarketCalendar.from_file(config.market_calendar_path),
    )


def _daemon_state_path(config: AgenticConfig, override: Path | None = None) -> Path:
    if override is not None:
        return override
    if config.daemon_state_path:
        return Path(config.daemon_state_path)
    service_root = os.environ.get("SERVICE_ROOT")
    if not service_root:
        raise RuntimeError("SERVICE_ROOT must be set for daemon state storage")
    return Path(service_root) / "rh_agentic_state.json"


def _daemon_state_json_payload(state: DaemonState) -> dict:
    return {
        "trading_day": state.trading_day,
        "last_warmup_at": state.last_warmup_at,
        "last_reconciliation_at": state.last_reconciliation_at,
        "lane_evaluations": dict(state.lane_evaluations),
        "live_order_attempts": state.live_order_attempts,
        "live_orders_submitted": state.live_orders_submitted,
        "live_notional_attempted": state.live_notional_attempted,
        "live_notional_submitted": state.live_notional_submitted,
        "pending_orders": [_pending_order_payload(order) for order in state.pending_orders],
    }


def _pending_order_payload(order: PendingOrderState) -> dict:
    return {
        "ref_id": order.ref_id,
        "symbol": order.symbol,
        "side": order.side,
        "status": order.status,
        "order_id": order.order_id,
        "dollar_amount": order.dollar_amount,
        "timestamp": order.timestamp,
    }


def _reconcile_daemon_state(account_number: str, client, state: DaemonState) -> dict:
    pending: list[PendingOrderState] = []
    lines: list[str] = []
    matched = 0
    for pending_order in state.pending_orders:
        order = None
        if pending_order.order_id:
            order = _fetch_equity_order(account_number, client, pending_order.order_id)
        if order is None:
            intent = _intent_from_pending_order(pending_order)
            if intent is not None:
                order = _find_matching_equity_order(account_number, client, intent, pending_order.timestamp)

        if order is None:
            pending.append(pending_order)
            lines.append(f"{pending_order.symbol}: unresolved pending order")
            continue

        matched += 1
        order_id = str(_first_present(order, "id", "order_id") or pending_order.order_id)
        status = str(_first_present(order, "state", "status") or pending_order.status)
        if _terminal_order_status(status):
            lines.append(f"{pending_order.symbol}: resolved terminal status={status} order_id={order_id}")
            continue
        pending.append(
            PendingOrderState(
                ref_id=pending_order.ref_id,
                symbol=pending_order.symbol,
                side=pending_order.side,
                status=status,
                order_id=order_id,
                dollar_amount=pending_order.dollar_amount,
                timestamp=pending_order.timestamp,
            )
        )
        lines.append(f"{pending_order.symbol}: confirmed pending status={status} order_id={order_id}")

    return {
        "checked": len(state.pending_orders),
        "matched": matched,
        "state": replace_state_pending(state, tuple(pending)),
        "lines": lines,
    }


def _intent_from_pending_order(order: PendingOrderState) -> OrderIntent | None:
    try:
        if order.dollar_amount > 0:
            return OrderIntent(order.symbol, order.side, dollar_amount=order.dollar_amount)
    except ValueError:
        return None
    return None


def _terminal_order_status(status: str) -> bool:
    return status.strip().lower() in {"filled", "cancelled", "canceled", "rejected", "failed", "voided"}


def _mcp_orders_arguments(account_number: str, args) -> dict[str, str]:
    arguments = {"account_number": account_number}
    for attr, key in (
        ("symbol", "symbol"),
        ("state", "state"),
        ("order_id", "order_id"),
        ("created_at_gte", "created_at_gte"),
        ("placed_agent", "placed_agent"),
    ):
        value = getattr(args, attr, None)
        if value:
            arguments[key] = str(value).strip()
    if "symbol" in arguments:
        arguments["symbol"] = arguments["symbol"].upper()
    return arguments


def _reconcile_order_result(account_number: str, client, result: OrderResult) -> OrderResult:
    if (not result.placed and result.status != "unconfirmed") or result.order_id:
        return result

    order = _find_matching_equity_order(account_number, client, result.intent, result.timestamp)
    if not order:
        return result

    raw = {"placement": result.raw, "reconciled_order": order}
    return replace(
        result,
        placed=True,
        order_id=str(_first_present(order, "id", "order_id") or ""),
        status=str(_first_present(order, "state", "status") or result.status),
        filled_quantity=_float_or_default(
            _first_present(order, "filled_quantity", "cumulative_quantity", "executed_quantity"),
            result.filled_quantity,
        ),
        average_price=_float_or_default(
            _first_present(order, "average_price", "executed_price"),
            result.average_price,
        ),
        raw=raw,
    )


def _find_matching_equity_order(
    account_number: str,
    client,
    intent: OrderIntent,
    created_at_gte: str | None = None,
) -> dict | None:
    arguments = {
        "account_number": account_number,
        "symbol": intent.symbol,
        "placed_agent": "agentic",
    }
    if created_at_gte:
        arguments["created_at_gte"] = str(created_at_gte).split("T", 1)[0]
    payload = client.call_tool("get_equity_orders", arguments)
    for order in _extract_order_rows(payload):
        if _order_matches_intent(order, intent):
            return order
    return None


def _order_matches_intent(order: dict, intent: OrderIntent) -> bool:
    if str(_first_present(order, "symbol", "instrument_symbol") or "").upper() != intent.symbol:
        return False
    if str(_first_present(order, "side") or "").lower() != intent.side:
        return False
    order_type = str(_first_present(order, "type", "order_type") or "").lower()
    if order_type and order_type != intent.order_type:
        return False
    if intent.dollar_amount is not None:
        dollars = _float_or_none(
            _first_present(order, "dollar_amount", "notional", "amount")
            or _get_nested(order, "dollar_based_amount", "amount")
        )
        return dollars is not None and abs(dollars - intent.dollar_amount) < 0.01
    if intent.quantity is not None:
        quantity = _float_or_none(_first_present(order, "quantity", "shares"))
        return quantity is not None and abs(quantity - intent.quantity) < 0.000001
    return False


def _read_journal_rows(path: str | Path) -> list[dict]:
    journal_path = Path(path)
    if not journal_path.exists():
        return []
    rows: list[dict] = []
    for line in journal_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _reconcile_journal_rows(
    account_number: str,
    client,
    rows: list[dict],
    symbol: str | None = None,
    limit: int = 20,
) -> list[dict]:
    events: list[dict] = []
    wanted_symbol = symbol.upper() if symbol else None
    executions = [
        row
        for row in rows
        if row.get("event_type") == "broker_execution"
        and isinstance(row.get("execution"), dict)
        and row["execution"].get("placed") is True
    ]
    for row in reversed(executions):
        if len(events) >= max(0, limit):
            break
        if wanted_symbol and str(row.get("symbol", "")).upper() != wanted_symbol:
            continue
        execution = row["execution"]
        order = None
        order_id = execution.get("order_id")
        if order_id:
            order = _fetch_equity_order(account_number, client, str(order_id))
        if order is None:
            intent = _intent_from_payload(execution.get("order_intent"))
            if intent is not None:
                order = _find_matching_equity_order(
                    account_number,
                    client,
                    intent,
                    str(row.get("timestamp") or ""),
                )
        if not order:
            continue
        events.append(
            {
                "event_type": "broker_reconciliation",
                "source": "mcp-reconcile-orders",
                "execution_timestamp": row.get("timestamp"),
                "dry_run": row.get("dry_run"),
                "symbol": order.get("symbol") or row.get("symbol"),
                "action": str(order.get("side") or row.get("action") or "").upper(),
                "order_id": _first_present(order, "id", "order_id"),
                "broker_status": _first_present(order, "state", "status"),
                "order": _order_status_payload(order),
            }
        )
    return events


def _fetch_equity_order(account_number: str, client, order_id: str) -> dict | None:
    payload = client.call_tool(
        "get_equity_orders",
        {"account_number": account_number, "order_id": order_id},
    )
    rows = _extract_order_rows(payload)
    return rows[0] if rows else None


def _intent_from_payload(payload) -> OrderIntent | None:
    if not isinstance(payload, dict):
        return None
    try:
        return OrderIntent(
            symbol=str(payload["symbol"]),
            side=str(payload["side"]),
            order_type=str(payload.get("type") or "market"),
            dollar_amount=_float_or_none(payload.get("dollar_amount")),
            quantity=_float_or_none(payload.get("quantity")),
            limit_price=_float_or_none(payload.get("limit_price")),
            market_hours=str(payload.get("market_hours") or "regular_hours"),
            time_in_force=str(payload.get("time_in_force") or "gfd"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _extract_order_rows(payload) -> list[dict]:
    if isinstance(payload, dict):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        for key in ("orders", "results", "equity_orders"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        if any(key in data for key in ("id", "order_id", "state", "status")):
            return [data]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _order_status_payload(order: dict) -> dict[str, object]:
    return {
        "order_id": _first_present(order, "id", "order_id"),
        "symbol": _first_present(order, "symbol", "instrument_symbol"),
        "side": _first_present(order, "side"),
        "type": _first_present(order, "type", "order_type"),
        "state": _first_present(order, "state", "status"),
        "quantity": _first_present(order, "quantity", "shares"),
        "filled_quantity": _first_present(
            order,
            "filled_quantity",
            "cumulative_quantity",
            "executed_quantity",
        ),
        "dollar_amount": (
            _first_present(order, "dollar_amount", "notional", "amount")
            or _get_nested(order, "dollar_based_amount", "amount")
        ),
        "average_price": _first_present(order, "average_price", "executed_price"),
        "last_transaction_at": _first_present(order, "last_transaction_at", "created_at", "created"),
        "placed_agent": _first_present(order, "placed_agent"),
    }


def _format_order_row(order: dict) -> str:
    order_id = _first_present(order, "id", "order_id") or "-"
    symbol = _first_present(order, "symbol", "instrument_symbol") or "-"
    side = _first_present(order, "side") or "-"
    state = _first_present(order, "state", "status") or "-"
    order_type = _first_present(order, "type", "order_type") or "-"
    quantity = _first_present(order, "quantity", "shares") or "-"
    filled = _first_present(order, "filled_quantity", "cumulative_quantity", "executed_quantity") or "-"
    dollars = (
        _first_present(order, "dollar_amount", "notional", "amount")
        or _get_nested(order, "dollar_based_amount", "amount")
        or "-"
    )
    average_price = _first_present(order, "average_price", "executed_price") or "-"
    created_at = _first_present(order, "last_transaction_at", "created_at", "created") or "-"
    return (
        f"{created_at} {symbol} {side} {order_type} state={state} "
        f"qty={quantity} filled={filled} dollars={dollars} avg={average_price} id={order_id}"
    )


def _first_present(payload: dict, *keys: str):
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _get_nested(payload: dict, *keys: str):
    value = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if value not in (None, "") else None


def _float_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_or_default(value, default):
    parsed = _float_or_none(value)
    return default if parsed is None else parsed


def _print_console_safe(value: str) -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(value.encode(encoding, errors="replace").decode(encoding))


if __name__ == "__main__":
    raise SystemExit(main())
