import json
import os
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from robinhood.agentic.backtest import run_daily_trend_backtest, run_daily_trend_portfolio_backtest
from robinhood.agentic.bot import AgenticBot
from robinhood.agentic.broker import AccountSnapshot, OrderIntent, OrderResult, OrderReview, PaperBroker, Position
from robinhood.agentic.cli import (
    _append_daily_daemon_completion,
    _apply_run_daily_what_if_overrides,
    _daily_daemon_completed_days,
    _daily_daemon_due,
    _daily_daemon_seconds_until_next_check,
    _daily_daemon_trade_day,
    _extract_order_rows,
    _format_order_row,
    _journal_place_once,
    _live_order_gates_enabled,
    _live_readiness_failures,
    _mcp_orders_arguments,
    _mcp_review_intent,
    _parse_daily_daemon_run_time,
    _reconcile_daemon_state,
    _reconcile_journal_rows,
    _reconcile_order_result,
    _run_daily_auto_place_orders,
    _run_daily_daemon_config,
    _run_daily_live_trading_enabled,
    build_parser,
)
from robinhood.agentic.config import (
    LIVE_ORDER_CONFIRMATION,
    AgenticConfig,
    LaneConfig,
    RiskConfig,
    SymbolConfig,
    get_personal_config_path,
    load_config,
    load_lanes,
    load_personal_config,
    load_symbols,
)
from robinhood.agentic.daemon import PersistentDaemon, StateBackedBroker
from robinhood.agentic.daemon_state import (
    DaemonState,
    DaemonStateStore,
    PendingOrderState,
    clear_pending_orders,
    daemon_state_summary,
    reset_trade_day_after_unresolved_order,
)
from robinhood.agentic.execution import plan_order_intent
from robinhood.agentic.journal import DecisionJournal
from robinhood.agentic.market_clock import MarketCalendar, MarketClock
from robinhood.agentic.market_data import (
    Candle,
    CandleCollector,
    QuoteCollector,
    StaticHistoricalMarketDataSource,
    StaticMarketDataSource,
)
from robinhood.agentic.mcp_broker import AgenticMcpEquityBroker
from robinhood.agentic.mcp_client import (
    JsonTokenStorage,
    StreamableHttpMcpToolClient,
    decode_mcp_tool_result,
    decode_mcp_tools_result,
)
from robinhood.agentic.paper import PaperAccount
from robinhood.agentic.quotes import JsonQuoteProvider, QuoteUnavailable
from robinhood.agentic.risk import RiskManager
from robinhood.agentic.session import (
    BrokerSession,
    DailyCandleBrokerSession,
    DailyPlanItem,
    PaperSession,
    SessionResult,
    _daily_plan_summary_line,
)
from robinhood.agentic.strategy import (
    CryptoScalpStrategy,
    DailyTrendFollowStrategy,
    Decision,
    QuoteSnapshot,
    SimpleMomentumStrategy,
    build_strategy,
)


class AgenticBotTests(unittest.TestCase):
    def test_load_symbols_normalizes_values(self):
        with self.subTest("json config"):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmp_dir:
                config_path = Path(tmp_dir) / "symbols.cfg"
                config_path.write_text(
                    json.dumps({"stocks": ["aapl", " MSFT "], "crypto": ["btc"]}),
                    encoding="utf-8",
                )

                symbols = load_symbols(config_path)

        self.assertEqual(symbols.stocks, ("AAPL", "MSFT"))
        self.assertEqual(symbols.crypto, ("BTC",))

    def test_load_lanes_supports_object_config(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "symbols.cfg"
            config_path.write_text(
                json.dumps(
                    {
                        "stocks": {
                            "symbols": ["aapl"],
                            "strategy": "simple_momentum",
                            "poll_seconds": 30,
                            "asset_class": "equity",
                        },
                        "scalps": {
                            "symbols": ["nvda"],
                            "strategy": "simple_momentum",
                            "poll_seconds": 5,
                        },
                    }
                ),
                encoding="utf-8",
            )

            lanes = load_lanes(config_path)

        self.assertEqual(tuple(lane.name for lane in lanes), ("stocks", "scalps"))
        self.assertEqual(lanes[0].symbols, ("AAPL",))
        self.assertEqual(lanes[0].poll_seconds, 30.0)
        self.assertEqual(lanes[1].symbols, ("NVDA",))

    def test_load_personal_config_supports_service_file_shape(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "rh_agentic.json"
            config_path.write_text(
                json.dumps(
                    {
                        "account_number": "123456789",
                        "broker": "agentic_mcp",
                        "mcp_url": "https://agent.robinhood.com/mcp/trading",
                        "mcp_bearer_token_env_var": "RH_MCP_TOKEN",
                        "mcp_token_store_path": "R:/service/rh_agentic_mcp_tokens.json",
                        "mcp_oauth_callback_port": 8766,
                        "mcp_oauth_scope": "trading",
                        "dry_run": True,
                        "live_trading_enabled": False,
                        "auto_place_orders": False,
                        "live_order_confirm": LIVE_ORDER_CONFIRMATION,
                        "journal_path": "R:/service/agentic_decisions.jsonl",
                        "quote_source_path": "R:/service/rh_quotes.json",
                        "daemon_state_path": "R:/service/rh_agentic_state.json",
                        "market_calendar_path": "R:/service/market_calendar.json",
                        "poll_seconds": 30,
                        "paper_starting_cash": 5000,
                        "pre_open_warmup_minutes": 10,
                        "regular_trading_only": True,
                    }
                ),
                encoding="utf-8",
            )

            config = load_personal_config(config_path)

        self.assertEqual(config.account_number, "123456789")
        self.assertEqual(config.broker, "agentic_mcp")
        self.assertEqual(config.mcp_url, "https://agent.robinhood.com/mcp/trading")
        self.assertEqual(config.mcp_bearer_token_env_var, "RH_MCP_TOKEN")
        self.assertEqual(config.mcp_token_store_path, "R:/service/rh_agentic_mcp_tokens.json")
        self.assertEqual(config.mcp_oauth_callback_port, 8766)
        self.assertEqual(config.mcp_oauth_scope, "trading")
        self.assertTrue(config.dry_run)
        self.assertFalse(config.live_trading_enabled)
        self.assertFalse(config.auto_place_orders)
        self.assertEqual(config.live_order_confirm, LIVE_ORDER_CONFIRMATION)
        self.assertEqual(config.journal_path, "R:/service/agentic_decisions.jsonl")
        self.assertEqual(config.quote_source_path, "R:/service/rh_quotes.json")
        self.assertEqual(config.daemon_state_path, "R:/service/rh_agentic_state.json")
        self.assertEqual(config.market_calendar_path, "R:/service/market_calendar.json")
        self.assertEqual(config.poll_seconds, 30.0)
        self.assertEqual(config.paper_starting_cash, 5000.0)
        self.assertEqual(config.pre_open_warmup_minutes, 10)
        self.assertTrue(config.regular_trading_only)

    def test_load_config_merges_repo_symbols_and_personal_risk(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp_dir:
            symbols_path = Path(tmp_dir) / "symbols.cfg"
            personal_path = Path(tmp_dir) / "rh_agentic.json"
            symbols_path.write_text(json.dumps({"stocks": ["AAPL"], "crypto": []}), encoding="utf-8")
            personal_path.write_text(
                json.dumps(
                    {
                        "account_number": "123456789",
                        "broker": "paper",
                        "dry_run": True,
                        "live_trading_enabled": True,
                        "auto_place_orders": True,
                        "live_order_confirm": LIVE_ORDER_CONFIRMATION,
                        "risk": {"max_trade_dollars": 7, "max_daily_trades": 2},
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(symbols_path, personal_path)

        self.assertEqual(config.account_number, "123456789")
        self.assertEqual(config.broker, "paper")
        self.assertTrue(config.live_trading_enabled)
        self.assertTrue(config.auto_place_orders)
        self.assertEqual(config.live_order_confirm, LIVE_ORDER_CONFIRMATION)
        self.assertEqual(config.symbols.stocks, ("AAPL",))
        self.assertEqual(config.risk.max_trade_dollars, 7.0)
        self.assertEqual(config.risk.max_daily_trades, 2)

    def test_load_config_reads_small_account_risk_controls(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp_dir:
            symbols_path = Path(tmp_dir) / "symbols.cfg"
            personal_path = Path(tmp_dir) / "rh_agentic.json"
            symbols_path.write_text(json.dumps({"stocks": ["SPY"], "crypto": []}), encoding="utf-8")
            personal_path.write_text(
                json.dumps(
                    {
                        "risk": {
                            "min_order_dollars": 1,
                            "max_trade_dollars": 15,
                            "max_daily_trades": 2,
                            "max_new_buys_per_day": 1,
                            "max_open_positions": 2,
                            "min_cash_reserve": 50,
                            "max_total_exposure_dollars": 50,
                        }
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(symbols_path, personal_path)

        self.assertEqual(config.risk.min_order_dollars, 1.0)
        self.assertEqual(config.risk.max_trade_dollars, 15.0)
        self.assertEqual(config.risk.max_daily_trades, 2)
        self.assertEqual(config.risk.max_new_buys_per_day, 1)
        self.assertEqual(config.risk.max_open_positions, 2)
        self.assertEqual(config.risk.min_cash_reserve, 50.0)
        self.assertEqual(config.risk.max_total_exposure_dollars, 50.0)

    def test_personal_config_path_uses_service_root(self):
        old_value = os.environ.get("SERVICE_ROOT")
        os.environ["SERVICE_ROOT"] = "R:/service"
        try:
            path = get_personal_config_path()
        finally:
            if old_value is None:
                os.environ.pop("SERVICE_ROOT", None)
            else:
                os.environ["SERVICE_ROOT"] = old_value

        self.assertEqual(path, Path("R:/service") / "rh_agentic.json")

    def test_mcp_review_parser_defaults(self):
        args = build_parser().parse_args(["mcp-review"])

        self.assertEqual(args.command, "mcp-review")
        self.assertEqual(args.symbol, "SPY")
        self.assertEqual(args.dollars, 1.0)

    def test_live_check_parser_defaults(self):
        args = build_parser().parse_args(["live-check"])

        self.assertEqual(args.command, "live-check")
        self.assertEqual(args.symbol, "SPY")
        self.assertEqual(args.dollars, 1.0)

    def test_mcp_place_once_parser_requires_explicit_order(self):
        args = build_parser().parse_args(["mcp-place-once", "--symbol", "spy", "--dollars", "1"])

        self.assertEqual(args.command, "mcp-place-once")
        self.assertEqual(args.symbol, "spy")
        self.assertEqual(args.dollars, 1.0)

    def test_run_daily_parser_supports_review_only(self):
        args = build_parser().parse_args(
            [
                "run-daily",
                "--candle-file",
                "candles.json",
                "--range",
                "6mo",
                "--review-only",
                "--what-if-max-open-positions",
                "2",
                "--what-if-max-total-exposure-dollars",
                "50",
            ]
        )

        self.assertEqual(args.command, "run-daily")
        self.assertEqual(args.candle_file, Path("candles.json"))
        self.assertEqual(args.range, "6mo")
        self.assertTrue(args.review_only)
        self.assertEqual(args.what_if_max_open_positions, 2)
        self.assertEqual(args.what_if_max_total_exposure_dollars, 50.0)

    def test_run_daily_daemon_parser_defaults(self):
        args = build_parser().parse_args(["run-daily-daemon", "--candle-file", "candles.json"])

        self.assertEqual(args.command, "run-daily-daemon")
        self.assertEqual(args.candle_file, Path("candles.json"))
        self.assertEqual(args.run_at, "09:35")
        self.assertEqual(args.timezone, "America/New_York")
        self.assertEqual(args.poll_seconds, 60.0)
        self.assertEqual(args.max_live_order_dollars, 5.0)
        self.assertFalse(args.rerun_today)
        self.assertFalse(args.review_only)

    def test_run_daily_daemon_parser_overrides(self):
        args = build_parser().parse_args(
            [
                "run-daily-daemon",
                "--candle-file",
                "candles.json",
                "--review-only",
                "--run-at",
                "10:15",
                "--timezone",
                "America/Chicago",
                "--poll-seconds",
                "5",
                "--max-iterations",
                "1",
                "--max-live-order-dollars",
                "5",
                "--rerun-today",
            ]
        )

        self.assertTrue(args.review_only)
        self.assertEqual(args.run_at, "10:15")
        self.assertEqual(args.timezone, "America/Chicago")
        self.assertEqual(args.poll_seconds, 5.0)
        self.assertEqual(args.max_iterations, 1)
        self.assertEqual(args.max_live_order_dollars, 5.0)
        self.assertTrue(args.rerun_today)

    def test_run_daemon_parser_defaults(self):
        args = build_parser().parse_args(["run-daemon", "--candle-file", "candles.json"])

        self.assertEqual(args.command, "run-daemon")
        self.assertEqual(args.candle_file, Path("candles.json"))
        self.assertEqual(args.range, "1y")
        self.assertEqual(args.max_live_order_dollars, 5.0)
        self.assertFalse(args.review_only)
        self.assertFalse(args.status_only)

    def test_market_clock_parser(self):
        args = build_parser().parse_args(["market-clock", "--timezone", "America/Chicago"])

        self.assertEqual(args.command, "market-clock")
        self.assertEqual(args.timezone, "America/Chicago")

    def test_daemon_state_parser(self):
        args = build_parser().parse_args(["daemon-state", "--state-file", "state.json", "--json"])

        self.assertEqual(args.command, "daemon-state")
        self.assertEqual(args.state_file, Path("state.json"))
        self.assertTrue(args.json)

    def test_daemon_reconcile_parser(self):
        args = build_parser().parse_args(["daemon-reconcile", "--state-file", "state.json", "--dry-run"])

        self.assertEqual(args.command, "daemon-reconcile")
        self.assertEqual(args.state_file, Path("state.json"))
        self.assertTrue(args.dry_run)

    def test_daemon_clear_pending_parser_requires_reason(self):
        args = build_parser().parse_args(["daemon-clear-pending", "--state-file", "state.json", "--reason", "manual"])

        self.assertEqual(args.command, "daemon-clear-pending")
        self.assertEqual(args.state_file, Path("state.json"))
        self.assertEqual(args.reason, "manual")

    def test_daemon_reset_trade_day_parser_requires_reason(self):
        args = build_parser().parse_args(["daemon-reset-trade-day", "--state-file", "state.json", "--reason", "manual"])

        self.assertEqual(args.command, "daemon-reset-trade-day")
        self.assertEqual(args.state_file, Path("state.json"))
        self.assertEqual(args.reason, "manual")

    def test_mcp_tools_parser_defaults_to_text(self):
        args = build_parser().parse_args(["mcp-tools", "--filter", "order"])

        self.assertEqual(args.command, "mcp-tools")
        self.assertEqual(args.filter, "order")
        self.assertFalse(args.json)

    def test_mcp_orders_parser_supports_filters(self):
        args = build_parser().parse_args(
            ["mcp-orders", "--symbol", "spy", "--state", "queued", "--placed-agent", "agentic"]
        )

        self.assertEqual(args.command, "mcp-orders")
        self.assertEqual(args.symbol, "spy")
        self.assertEqual(args.state, "queued")
        self.assertEqual(args.placed_agent, "agentic")

    def test_mcp_reconcile_orders_parser_defaults_to_append(self):
        args = build_parser().parse_args(["mcp-reconcile-orders", "--symbol", "spy"])

        self.assertEqual(args.command, "mcp-reconcile-orders")
        self.assertEqual(args.symbol, "spy")
        self.assertFalse(args.dry_run)

    def test_mcp_review_intent_validates_dollars(self):
        intent = _mcp_review_intent("spy", 1.234)

        self.assertEqual(intent.symbol, "SPY")
        self.assertEqual(intent.side, "buy")
        self.assertEqual(intent.dollar_amount, 1.23)
        with self.assertRaisesRegex(SystemExit, "greater than 0"):
            _mcp_review_intent("SPY", 0)

    def test_live_readiness_fails_when_live_gates_disabled(self):
        intent = OrderIntent("SPY", "buy", dollar_amount=1.0)
        failures = _live_readiness_failures(
            AgenticConfig(
                broker="paper",
                dry_run=True,
                live_trading_enabled=False,
                auto_place_orders=False,
                symbols=SymbolConfig(stocks=("SPY",)),
            ),
            AccountSnapshot(cash=100.0),
            OrderReview(intent, approved=True, reason="approved"),
            intent,
        )

        self.assertIn("broker must be agentic_mcp", failures)
        self.assertIn("dry_run must be false", failures)
        self.assertIn("live_trading_enabled must be true", failures)
        self.assertIn("auto_place_orders must be true", failures)
        self.assertIn("live_order_confirm must match required confirmation phrase", failures)

    def test_live_readiness_passes_for_strict_live_config(self):
        intent = OrderIntent("SPY", "buy", dollar_amount=1.0)
        failures = _live_readiness_failures(
            AgenticConfig(
                broker="agentic_mcp",
                dry_run=False,
                live_trading_enabled=True,
                auto_place_orders=True,
                live_order_confirm=LIVE_ORDER_CONFIRMATION,
                symbols=SymbolConfig(stocks=("SPY",)),
                risk=RiskConfig(
                    min_order_dollars=1.0,
                    max_trade_dollars=10.0,
                    max_daily_trades=1,
                    max_new_buys_per_day=1,
                    max_open_positions=1,
                    min_cash_reserve=50.0,
                    max_total_exposure_dollars=25.0,
                ),
            ),
            AccountSnapshot(cash=100.0),
            OrderReview(intent, approved=True, reason="approved"),
            intent,
        )

        self.assertEqual(failures, [])

    def test_live_order_gates_require_confirmation_phrase(self):
        config = AgenticConfig(
            broker="agentic_mcp",
            dry_run=False,
            live_trading_enabled=True,
            auto_place_orders=True,
        )

        self.assertFalse(_live_order_gates_enabled(config))
        self.assertTrue(
            _live_order_gates_enabled(
                AgenticConfig(
                    broker="agentic_mcp",
                    dry_run=False,
                    live_trading_enabled=True,
                    auto_place_orders=True,
                    live_order_confirm=LIVE_ORDER_CONFIRMATION,
                )
            )
        )

    def test_run_daily_review_only_forces_live_controls_off(self):
        config = AgenticConfig(
            broker="agentic_mcp",
            dry_run=False,
            live_trading_enabled=True,
            auto_place_orders=True,
            live_order_confirm=LIVE_ORDER_CONFIRMATION,
        )

        self.assertTrue(_run_daily_live_trading_enabled(config, review_only=False))
        self.assertTrue(_run_daily_auto_place_orders(config, review_only=False))
        self.assertFalse(_run_daily_live_trading_enabled(config, review_only=True))
        self.assertFalse(_run_daily_auto_place_orders(config, review_only=True))

    def test_run_daily_what_if_override_requires_review_only(self):
        config = AgenticConfig(risk=RiskConfig(max_open_positions=1))
        args = build_parser().parse_args(
            ["run-daily", "--candle-file", "candles.json", "--what-if-max-total-exposure-dollars", "50"]
        )

        with self.assertRaisesRegex(SystemExit, "require --review-only"):
            _apply_run_daily_what_if_overrides(config, args)

    def test_run_daily_what_if_override_updates_risk_limits(self):
        config = AgenticConfig(
            risk=RiskConfig(
                max_open_positions=1,
                max_total_exposure_dollars=10.0,
            )
        )
        args = build_parser().parse_args(
            [
                "run-daily",
                "--candle-file",
                "candles.json",
                "--review-only",
                "--what-if-max-open-positions",
                "2",
                "--what-if-max-total-exposure-dollars",
                "50",
            ]
        )

        updated = _apply_run_daily_what_if_overrides(config, args)

        self.assertEqual(updated.risk.max_open_positions, 2)
        self.assertEqual(updated.risk.max_total_exposure_dollars, 50.0)
        self.assertEqual(config.risk.max_open_positions, 1)
        self.assertEqual(config.risk.max_total_exposure_dollars, 10.0)

    def test_run_daily_what_if_rejects_negative_exposure_override(self):
        config = AgenticConfig(risk=RiskConfig(max_total_exposure_dollars=10.0))
        args = build_parser().parse_args(
            [
                "run-daily",
                "--candle-file",
                "candles.json",
                "--review-only",
                "--what-if-max-total-exposure-dollars",
                "-1",
            ]
        )

        with self.assertRaisesRegex(SystemExit, "0 or greater"):
            _apply_run_daily_what_if_overrides(config, args)

    def test_run_daily_daemon_config_caps_max_trade_dollars(self):
        config = AgenticConfig(risk=RiskConfig(max_trade_dollars=15.0))

        updated = _run_daily_daemon_config(config, 5.0)

        self.assertEqual(updated.risk.max_trade_dollars, 5.0)
        self.assertEqual(config.risk.max_trade_dollars, 15.0)

    def test_run_daily_daemon_config_does_not_raise_lower_cap(self):
        config = AgenticConfig(risk=RiskConfig(max_trade_dollars=3.0))

        updated = _run_daily_daemon_config(config, 5.0)

        self.assertEqual(updated.risk.max_trade_dollars, 3.0)

    def test_daily_daemon_timing_helpers(self):
        tz = ZoneInfo("America/New_York")
        run_time = _parse_daily_daemon_run_time("09:35")
        before = datetime(2026, 6, 29, 9, 30, tzinfo=tz)
        after = datetime(2026, 6, 29, 9, 36, tzinfo=tz)
        weekend = datetime(2026, 7, 4, 10, 0, tzinfo=tz)

        self.assertEqual(_daily_daemon_trade_day(before), "2026-06-29")
        self.assertIsNone(_daily_daemon_trade_day(weekend))
        self.assertFalse(_daily_daemon_due(before, run_time, set()))
        self.assertTrue(_daily_daemon_due(after, run_time, set()))
        self.assertFalse(_daily_daemon_due(after, run_time, {"2026-06-29"}))
        self.assertEqual(_daily_daemon_seconds_until_next_check(before, run_time), 300.0)

    def test_daily_daemon_completion_marker_persists_completed_day(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            journal = DecisionJournal(journal_path)
            result = SessionResult(
                iterations=1,
                decisions=5,
                skipped_quotes=0,
                collection_errors=0,
                paper_cash=99.0,
                positions={},
            )

            _append_daily_daemon_completion(journal, "2026-06-29", result, review_only=False)
            completed_days = _daily_daemon_completed_days(journal_path)

        self.assertEqual(completed_days, {"2026-06-29"})

    def test_daily_daemon_run_time_rejects_invalid_value(self):
        with self.assertRaisesRegex(SystemExit, "HH:MM"):
            _parse_daily_daemon_run_time("25:00")

    def test_market_clock_states_and_next_wakeup(self):
        clock = MarketClock(pre_open_warmup_minutes=5)
        tz = ZoneInfo("America/New_York")

        closed = clock.status(datetime(2026, 6, 29, 8, 0, tzinfo=tz))
        warmup = clock.status(datetime(2026, 6, 29, 9, 26, tzinfo=tz))
        open_ = clock.status(datetime(2026, 6, 29, 10, 0, tzinfo=tz))
        after_close = clock.status(datetime(2026, 6, 29, 16, 1, tzinfo=tz))
        weekend = clock.status(datetime(2026, 7, 4, 10, 0, tzinfo=tz))

        self.assertEqual(closed.state, "closed")
        self.assertEqual(closed.next_wakeup.hour, 9)
        self.assertEqual(closed.next_wakeup.minute, 25)
        self.assertEqual(warmup.state, "warmup")
        self.assertEqual(open_.state, "open")
        self.assertTrue(open_.trading_allowed)
        self.assertEqual(after_close.state, "after_close")
        self.assertEqual(weekend.state, "closed")
        self.assertEqual(weekend.next_open.date().isoformat(), "2026-07-06")

    def test_market_calendar_supports_closed_dates_and_half_days(self):
        import tempfile

        tz = ZoneInfo("America/New_York")
        with tempfile.TemporaryDirectory() as tmp_dir:
            calendar_path = Path(tmp_dir) / "market_calendar.json"
            calendar_path.write_text(
                json.dumps(
                    {
                        "closed_dates": ["2026-07-03"],
                        "half_days": {"2026-11-27": "13:00"},
                    }
                ),
                encoding="utf-8",
            )
            clock = MarketClock(calendar=MarketCalendar.from_file(calendar_path))

        holiday = clock.status(datetime(2026, 7, 3, 10, 0, tzinfo=tz))
        half_day_open = clock.status(datetime(2026, 11, 27, 12, 0, tzinfo=tz))
        half_day_closed = clock.status(datetime(2026, 11, 27, 13, 1, tzinfo=tz))

        self.assertEqual(holiday.state, "closed")
        self.assertEqual(holiday.next_open.date().isoformat(), "2026-07-06")
        self.assertEqual(half_day_open.state, "open")
        self.assertEqual(half_day_open.next_close.hour, 13)
        self.assertEqual(half_day_closed.state, "after_close")

    def test_daemon_state_store_persists_and_rolls_trade_day(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = DaemonStateStore(Path(tmp_dir) / "state.json")
            state = DaemonState(
                trading_day="2026-06-29",
                live_order_attempts=1,
                pending_orders=(PendingOrderState("ref", "QQQ", "buy", "unconfirmed", dollar_amount=5.0),),
            )
            store.save(state)

            loaded = store.load()
            rolled = loaded.for_trade_day("2026-06-30")

        self.assertEqual(loaded.live_order_attempts, 1)
        self.assertEqual(loaded.pending_orders[0].symbol, "QQQ")
        self.assertEqual(rolled.trading_day, "2026-06-30")
        self.assertEqual(rolled.live_order_attempts, 0)
        self.assertEqual(rolled.pending_orders, ())

    def test_daemon_state_summary_and_clear_pending_orders(self):
        state = DaemonState(
            trading_day="2026-06-29",
            live_order_attempts=1,
            live_orders_submitted=1,
            live_notional_attempted=5.0,
            live_notional_submitted=5.0,
            pending_orders=(
                PendingOrderState(
                    "ref-1",
                    "QQQ",
                    "buy",
                    "submitted",
                    order_id="order-1",
                    dollar_amount=5.0,
                    timestamp="2026-06-29T13:30:00Z",
                ),
            ),
        )

        summary = daemon_state_summary(state, "state.json")
        cleared = clear_pending_orders(state)

        self.assertIn("[daemon-state] path=state.json", summary)
        self.assertIn("pending_orders=1", summary)
        self.assertIn("symbol=QQQ", summary)
        self.assertEqual(cleared.pending_orders, ())
        self.assertEqual(cleared.live_order_attempts, 1)
        self.assertTrue(cleared.last_reconciliation_at)

    def test_reset_trade_day_after_unresolved_order_clears_retry_blockers(self):
        state = DaemonState(
            trading_day="2026-06-30",
            last_warmup_at="2026-06-30T09:25:00-04:00",
            lane_evaluations={"stocks": "2026-06-30"},
            live_order_attempts=1,
            live_orders_submitted=0,
            live_notional_attempted=5.0,
            pending_orders=(PendingOrderState("ref", "QQQ", "buy", "unconfirmed", dollar_amount=5.0),),
        )

        reset = reset_trade_day_after_unresolved_order(state)

        self.assertEqual(reset.trading_day, "2026-06-30")
        self.assertEqual(reset.last_warmup_at, "2026-06-30T09:25:00-04:00")
        self.assertEqual(reset.lane_evaluations, {})
        self.assertEqual(reset.live_order_attempts, 0)
        self.assertEqual(reset.live_notional_attempted, 0.0)
        self.assertEqual(reset.pending_orders, ())
        self.assertTrue(reset.last_reconciliation_at)

    def test_reconcile_daemon_state_keeps_unresolved_pending_order(self):
        state = DaemonState(
            pending_orders=(
                PendingOrderState(
                    "ref-1",
                    "QQQ",
                    "buy",
                    "submitted",
                    order_id="missing",
                    dollar_amount=5.0,
                    timestamp="2026-06-29T13:30:00Z",
                ),
            )
        )
        client = _FakeMcpClient({"get_equity_orders": {"data": {"orders": []}}})

        result = _reconcile_daemon_state("acct", client, state)

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["matched"], 0)
        self.assertEqual(len(result["state"].pending_orders), 1)
        self.assertIn("unresolved pending order", result["lines"][0])

    def test_reconcile_daemon_state_resolves_terminal_order(self):
        state = DaemonState(
            pending_orders=(
                PendingOrderState(
                    "ref-1",
                    "QQQ",
                    "buy",
                    "submitted",
                    order_id="order-1",
                    dollar_amount=5.0,
                    timestamp="2026-06-29T13:30:00Z",
                ),
            )
        )
        client = _FakeMcpClient(
            {
                "get_equity_orders": {
                    "data": {
                        "orders": [
                            {
                                "id": "order-1",
                                "symbol": "QQQ",
                                "side": "buy",
                                "type": "market",
                                "state": "filled",
                                "dollar_amount": 5.0,
                            }
                        ]
                    }
                }
            }
        )

        result = _reconcile_daemon_state("acct", client, state)

        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["state"].pending_orders, ())
        self.assertIn("resolved terminal status=filled", result["lines"][0])

    def test_reconcile_daemon_state_updates_confirmed_pending_order(self):
        state = DaemonState(
            pending_orders=(
                PendingOrderState(
                    "ref-1",
                    "IWM",
                    "buy",
                    "unconfirmed",
                    dollar_amount=5.0,
                    timestamp="2026-06-29T13:30:00Z",
                ),
            )
        )
        client = _FakeMcpClient(
            {
                "get_equity_orders": {
                    "data": {
                        "orders": [
                            {
                                "id": "order-2",
                                "symbol": "IWM",
                                "side": "buy",
                                "type": "market",
                                "state": "queued",
                                "dollar_amount": 5.0,
                            }
                        ]
                    }
                }
            }
        )

        result = _reconcile_daemon_state("acct", client, state)
        pending = result["state"].pending_orders

        self.assertEqual(result["matched"], 1)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].order_id, "order-2")
        self.assertEqual(pending[0].status, "queued")

    def test_state_backed_broker_blocks_after_submitted_pending_order(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = DaemonStateStore(Path(tmp_dir) / "state.json")
            store.save(DaemonState(trading_day="2026-06-29"))
            broker = StateBackedBroker(
                _FakeConfirmedBroker(cash=100.0),
                store,
                AgenticConfig(risk=RiskConfig(max_live_order_attempts_per_day=1, max_live_notional_per_day=10.0)),
            )

            first = broker.place_order(OrderIntent("QQQ", "buy", dollar_amount=5.0), price=100.0)
            second = broker.place_order(OrderIntent("IWM", "buy", dollar_amount=5.0), price=100.0)
            state = store.load()

        self.assertTrue(first.placed)
        self.assertFalse(second.placed)
        self.assertEqual(second.status, "rejected")
        self.assertIn("pending or unconfirmed", second.reason)
        self.assertEqual(state.live_order_attempts, 1)
        self.assertEqual(state.live_orders_submitted, 1)

    def test_state_backed_broker_reconciles_before_persisting_pending_order(self):
        import tempfile

        def reconcile(result):
            return replace(result, placed=True, status="queued", order_id="order-1")

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = DaemonStateStore(Path(tmp_dir) / "state.json")
            store.save(DaemonState(trading_day="2026-06-30"))
            broker = StateBackedBroker(
                _FakePlacedBroker(cash=100.0),
                store,
                AgenticConfig(risk=RiskConfig(max_live_order_attempts_per_day=1, max_live_notional_per_day=10.0)),
                order_result_reconciler=reconcile,
            )

            result = broker.place_order(OrderIntent("QQQ", "buy", dollar_amount=5.0), price=100.0)
            state = store.load()

        self.assertTrue(result.placed)
        self.assertEqual(result.order_id, "order-1")
        self.assertEqual(state.pending_orders[0].status, "queued")
        self.assertEqual(state.pending_orders[0].order_id, "order-1")

    def test_state_backed_broker_enforces_daily_attempt_limit(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = DaemonStateStore(Path(tmp_dir) / "state.json")
            store.save(DaemonState(trading_day="2026-06-29", live_order_attempts=1))
            broker = StateBackedBroker(
                _FakeConfirmedBroker(cash=100.0),
                store,
                AgenticConfig(risk=RiskConfig(max_live_order_attempts_per_day=1, max_live_notional_per_day=10.0)),
            )

            result = broker.place_order(OrderIntent("IWM", "buy", dollar_amount=5.0), price=100.0)

        self.assertFalse(result.placed)
        self.assertEqual(result.status, "rejected")
        self.assertIn("daily live order attempt limit", result.reason)

    def test_state_backed_broker_blocks_when_pending_order_exists(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = DaemonStateStore(Path(tmp_dir) / "state.json")
            store.save(
                DaemonState(
                    trading_day="2026-06-29",
                    pending_orders=(PendingOrderState("ref", "QQQ", "buy", "unconfirmed"),),
                )
            )
            broker = StateBackedBroker(
                _FakeConfirmedBroker(cash=100.0),
                store,
                AgenticConfig(risk=RiskConfig(max_live_order_attempts_per_day=2)),
            )

            result = broker.place_order(OrderIntent("IWM", "buy", dollar_amount=5.0), price=100.0)

        self.assertFalse(result.placed)
        self.assertEqual(result.status, "rejected")
        self.assertIn("pending or unconfirmed", result.reason)

    def test_persistent_daemon_runs_daily_lane_once_per_trade_day(self):
        import tempfile

        tz = ZoneInfo("America/New_York")
        candles = tuple(_daily_candles("QQQ", [100 + index for index in range(60)]))
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "state.json"
            candle_path = Path(tmp_dir) / "candles.json"
            journal_path = Path(tmp_dir) / "journal.jsonl"
            store = DaemonStateStore(state_path)
            config = AgenticConfig(
                broker="agentic_mcp",
                dry_run=False,
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("QQQ",)),
                lanes=(LaneConfig("stocks", symbols=("QQQ",), strategy="daily_trend_follow"),),
                risk=RiskConfig(max_trade_dollars=5.0, max_live_order_attempts_per_day=1),
            )
            daemon = PersistentDaemon(
                config=config,
                state_store=store,
                broker_factory=lambda _max_attempts: _FakeConfirmedBroker(cash=100.0),
                candle_file=candle_path,
                clock=MarketClock(pre_open_warmup_minutes=5),
                candle_source=StaticHistoricalMarketDataSource({"QQQ": candles}),
                now_fn=lambda: datetime(2026, 6, 29, 10, 0, tzinfo=tz),
                sleep_fn=lambda _seconds: None,
            )

            first = daemon.run(max_iterations=1)
            second = daemon.run(max_iterations=1)
            state = store.load()

        self.assertEqual(first.decisions, 1)
        self.assertEqual(second.decisions, 0)
        self.assertEqual(state.lane_evaluations["stocks"], "2026-06-29")
        self.assertEqual(state.live_order_attempts, 1)

    def test_journal_place_once_writes_execution_event(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            config = AgenticConfig(journal_path=str(journal_path), dry_run=False)
            intent = OrderIntent("SPY", "buy", dollar_amount=1.0)
            result = OrderResult(
                intent=intent,
                placed=True,
                status="submitted",
                reason="mcp order submitted",
                order_id="order-1",
            )

            _journal_place_once(config, result)
            row = json.loads(journal_path.read_text(encoding="utf-8"))

        self.assertEqual(row["event_type"], "broker_execution")
        self.assertEqual(row["source"], "mcp-place-once")
        self.assertEqual(row["symbol"], "SPY")
        self.assertEqual(row["action"], "BUY")
        self.assertEqual(row["execution"]["broker_status"], "submitted")
        self.assertEqual(row["execution"]["order_id"], "order-1")
        self.assertIn("timestamp", row)

    def test_strategy_buys_on_positive_momentum(self):
        strategy = SimpleMomentumStrategy(buy_threshold_pct=1.0, target_dollars=10.0)

        decision = strategy.evaluate(QuoteSnapshot("AAPL", price=102.0, previous_close=100.0))

        self.assertEqual(decision.action, "BUY")
        self.assertEqual(decision.target_dollars, 10.0)

    def test_strategy_holds_without_previous_close(self):
        strategy = SimpleMomentumStrategy()

        decision = strategy.evaluate(QuoteSnapshot("AAPL", price=102.0))

        self.assertEqual(decision.action, "HOLD")
        self.assertIn("missing previous close", decision.reason)

    def test_crypto_scalp_warms_up_before_trading(self):
        strategy = CryptoScalpStrategy()

        decision = strategy.evaluate(QuoteSnapshot("BTC", price=100.0))

        self.assertEqual(decision.action, "HOLD")
        self.assertIn("warming up", decision.reason)

    def test_crypto_scalp_buys_on_short_term_edge(self):
        strategy = CryptoScalpStrategy(
            fast_period=2,
            slow_period=4,
            rsi_period=3,
            min_edge_pct=0.05,
            buy_rsi_max=100.0,
            target_dollars=10.0,
        )
        prices = [100.0, 99.8, 100.1, 100.4, 100.8]

        decision = None
        for price in prices:
            decision = strategy.evaluate(QuoteSnapshot("BTC", price=price))

        self.assertEqual(decision.action, "BUY")
        self.assertEqual(decision.target_dollars, 10.0)

    def test_crypto_scalp_sells_on_take_profit(self):
        strategy = CryptoScalpStrategy(
            fast_period=2,
            slow_period=4,
            rsi_period=3,
            min_edge_pct=0.05,
            buy_rsi_max=100.0,
            take_profit_pct=0.2,
            target_dollars=10.0,
        )
        for price in [100.0, 99.8, 100.1, 100.4, 100.8]:
            strategy.evaluate(QuoteSnapshot("BTC", price=price))

        decision = strategy.evaluate(QuoteSnapshot("BTC", price=101.1))

        self.assertEqual(decision.action, "SELL")
        self.assertIn("take profit", decision.reason)

    def test_daily_trend_follow_buys_on_positive_daily_trend(self):
        strategy = DailyTrendFollowStrategy(
            short_period=3,
            long_period=5,
            atr_period=3,
            min_trend_pct=0.01,
            target_dollars=10.0,
        )
        candles = _daily_candles("SPY", [100, 101, 102, 103, 104, 105])

        decision = strategy.evaluate_candles("SPY", candles)

        self.assertEqual(decision.action, "BUY")
        self.assertEqual(decision.target_dollars, 10.0)
        self.assertIn("daily trend entry", decision.reason)

    def test_daily_trend_follow_sells_when_close_breaks_long_ema(self):
        strategy = DailyTrendFollowStrategy(
            short_period=3,
            long_period=5,
            atr_period=3,
            min_trend_pct=0.01,
        )
        candles = _daily_candles("SPY", [100, 101, 102, 103, 104, 95])

        decision = strategy.evaluate_candles(
            "SPY",
            candles,
            has_position=True,
            entry_price=100.0,
            peak_price=104.0,
        )

        self.assertEqual(decision.action, "SELL")
        self.assertIn("below ema", decision.reason)

    def test_build_strategy_supports_daily_trend_follow(self):
        strategy = build_strategy("daily_trend_follow", target_dollars=9.0)

        self.assertIsInstance(strategy, DailyTrendFollowStrategy)
        self.assertEqual(strategy.target_dollars, 9.0)

    def test_bot_analyzes_daily_candles(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            config = AgenticConfig(
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("SPY",)),
                risk=RiskConfig(max_trade_dollars=10.0),
            )
            bot = AgenticBot(config)

            entry = bot.analyze_candles(
                "SPY",
                _daily_candles("SPY", [100 + index for index in range(60)]),
                strategy_name="daily_trend_follow",
            )

        self.assertEqual(entry.decision["action"], "BUY")
        self.assertEqual(entry.quote["symbol"], "SPY")
        self.assertEqual(entry.quote["price"], 159)

    def test_risk_rejects_unlisted_symbol(self):
        config = AgenticConfig(symbols=SymbolConfig(stocks=("AAPL",)))
        manager = RiskManager(config)

        result = manager.evaluate(Decision("TSLA", "BUY", 1.0, "test", target_dollars=5.0))

        self.assertFalse(result.approved)
        self.assertIn("not in allowed", result.reason)

    def test_risk_allows_configured_crypto_symbol(self):
        config = AgenticConfig(symbols=SymbolConfig(crypto=("BTC",)))
        manager = RiskManager(config)

        result = manager.evaluate(Decision("BTC", "BUY", 1.0, "test", target_dollars=5.0))

        self.assertTrue(result.approved)

    def test_risk_rejects_trade_size_above_limit(self):
        config = AgenticConfig(
            symbols=SymbolConfig(stocks=("AAPL",)),
            risk=RiskConfig(max_trade_dollars=5.0),
        )
        manager = RiskManager(config)

        result = manager.evaluate(Decision("AAPL", "BUY", 1.0, "test", target_dollars=10.0))

        self.assertFalse(result.approved)
        self.assertIn("max trade size", result.reason)

    def test_risk_rejects_trade_size_below_minimum(self):
        config = AgenticConfig(
            symbols=SymbolConfig(stocks=("AAPL",)),
            risk=RiskConfig(min_order_dollars=1.0, max_trade_dollars=5.0),
        )
        manager = RiskManager(config)

        result = manager.evaluate(Decision("AAPL", "BUY", 1.0, "test", target_dollars=0.5))

        self.assertFalse(result.approved)
        self.assertIn("minimum order size", result.reason)

    def test_order_intent_requires_one_sizing_field(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            OrderIntent("SPY", "buy")

        with self.assertRaisesRegex(ValueError, "exactly one"):
            OrderIntent("SPY", "buy", dollar_amount=10.0, quantity=1.0)

    def test_paper_broker_reviews_and_places_fractional_buy(self):
        broker = PaperBroker(starting_cash=100.0)
        intent = OrderIntent("spy", "buy", dollar_amount=10.0, ref_id="order-1")

        review = broker.review_order(intent, price=100.0)
        result = broker.place_order(intent, price=100.0)
        snapshot = broker.get_account_snapshot()

        self.assertTrue(review.approved)
        self.assertAlmostEqual(review.estimated_quantity, 0.1)
        self.assertTrue(result.placed)
        self.assertEqual(result.order_id, "order-1")
        self.assertAlmostEqual(snapshot.cash, 90.0)
        self.assertAlmostEqual(snapshot.positions["SPY"].quantity, 0.1)

    def test_paper_broker_rejects_buy_above_cash(self):
        broker = PaperBroker(starting_cash=5.0)
        intent = OrderIntent("SPY", "buy", dollar_amount=10.0)

        result = broker.place_order(intent, price=100.0)

        self.assertFalse(result.placed)
        self.assertEqual(result.status, "rejected")
        self.assertIn("insufficient", result.reason)

    def test_paper_broker_sells_existing_position_only(self):
        broker = PaperBroker(starting_cash=100.0)
        broker.place_order(OrderIntent("SPY", "buy", dollar_amount=10.0), price=100.0)

        sell = broker.place_order(OrderIntent("SPY", "sell", quantity=0.05), price=110.0)
        rejected = broker.place_order(OrderIntent("SPY", "sell", quantity=1.0), price=110.0)
        snapshot = broker.get_account_snapshot()

        self.assertTrue(sell.placed)
        self.assertAlmostEqual(sell.filled_quantity, 0.05)
        self.assertAlmostEqual(snapshot.positions["SPY"].quantity, 0.05)
        self.assertFalse(rejected.placed)
        self.assertIn("exceed", rejected.reason)

    def test_plan_order_intent_sizes_buy_with_cash_reserve(self):
        broker = PaperBroker(starting_cash=55.0)
        decision = Decision("SPY", "BUY", 1.0, "test", target_dollars=10.0)

        plan = plan_order_intent(
            decision,
            broker.get_account_snapshot(),
            RiskConfig(
                min_order_dollars=1.0,
                max_trade_dollars=15.0,
                min_cash_reserve=50.0,
                max_open_positions=2,
                max_total_exposure_dollars=50.0,
            ),
            price=100.0,
        )

        self.assertTrue(plan.approved)
        self.assertEqual(plan.intent.side, "buy")
        self.assertEqual(plan.intent.dollar_amount, 5.0)

    def test_plan_order_intent_rejects_when_open_position_limit_reached(self):
        broker = PaperBroker(starting_cash=100.0)
        broker.place_order(OrderIntent("SPY", "buy", dollar_amount=10.0), price=100.0)

        plan = plan_order_intent(
            Decision("QQQ", "BUY", 1.0, "test", target_dollars=10.0),
            broker.get_account_snapshot(),
            RiskConfig(max_open_positions=1, min_cash_reserve=50.0),
            price=200.0,
        )

        self.assertFalse(plan.approved)
        self.assertIn("max open positions", plan.reason)

    def test_plan_order_intent_creates_sell_for_existing_quantity(self):
        broker = PaperBroker(starting_cash=100.0)
        broker.place_order(OrderIntent("SPY", "buy", dollar_amount=10.0), price=100.0)

        plan = plan_order_intent(
            Decision("SPY", "SELL", 1.0, "test"),
            broker.get_account_snapshot(),
            RiskConfig(),
            price=101.0,
        )

        self.assertTrue(plan.approved)
        self.assertEqual(plan.intent.side, "sell")
        self.assertAlmostEqual(plan.intent.quantity, 0.1)

    def test_plan_order_intent_rejects_sell_without_position(self):
        plan = plan_order_intent(
            Decision("SPY", "SELL", 1.0, "test"),
            PaperBroker(starting_cash=100.0).get_account_snapshot(),
            RiskConfig(),
            price=101.0,
        )

        self.assertFalse(plan.approved)
        self.assertIn("no open", plan.reason)

    def test_agentic_mcp_broker_reads_account_snapshot(self):
        client = _FakeMcpClient(
            {
                "get_portfolio": {"buying_power": "100.00"},
                "get_equity_positions": {"results": [{"symbol": "SPY", "quantity": "0.1", "average_cost": "100.0"}]},
            }
        )
        broker = AgenticMcpEquityBroker("123", client)

        snapshot = broker.get_account_snapshot()

        self.assertEqual(snapshot.cash, 100.0)
        self.assertAlmostEqual(snapshot.positions["SPY"].quantity, 0.1)

    def test_agentic_mcp_broker_reads_data_wrapped_account_snapshot(self):
        client = _FakeMcpClient(
            {
                "get_portfolio": {
                    "data": {
                        "cash": "100.00",
                        "buying_power": {"buying_power": "125.00"},
                    },
                    "guide": {},
                },
                "get_equity_positions": {
                    "data": {"positions": [{"symbol": "SPY", "quantity": "0.1", "average_cost": "100.0"}]},
                    "guide": {},
                },
            }
        )
        broker = AgenticMcpEquityBroker("123", client)

        snapshot = broker.get_account_snapshot()

        self.assertEqual(snapshot.cash, 100.0)
        self.assertAlmostEqual(snapshot.positions["SPY"].quantity, 0.1)

    def test_agentic_mcp_broker_reads_nested_buying_power_when_cash_missing(self):
        client = _FakeMcpClient(
            {
                "get_portfolio": {
                    "data": {"buying_power": {"buying_power": "125.00"}},
                    "guide": {},
                },
                "get_equity_positions": {"data": {"positions": []}},
            }
        )
        broker = AgenticMcpEquityBroker("123", client)

        snapshot = broker.get_account_snapshot()

        self.assertEqual(snapshot.cash, 125.0)

    def test_agentic_mcp_broker_review_only_does_not_place(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": True}]},
                "review_equity_order": {"status": "approved", "estimated_quantity": "0.1"},
                "place_equity_order": {"id": "live-order"},
            }
        )
        broker = AgenticMcpEquityBroker("123", client)

        result = broker.place_order(OrderIntent("SPY", "buy", dollar_amount=10.0), price=100.0)

        self.assertFalse(result.placed)
        self.assertEqual(result.status, "reviewed")
        self.assertNotIn("place_equity_order", client.calls)

    def test_agentic_mcp_broker_review_uses_mcp_order_schema(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": True}]},
                "review_equity_order": {"status": "approved", "estimated_quantity": "0.1"},
            }
        )
        broker = AgenticMcpEquityBroker("123", client)

        broker.review_order(
            OrderIntent("SPY", "buy", dollar_amount=10.0, ref_id="local-order-id"),
            price=100.0,
        )

        self.assertEqual(
            client.call_arguments["review_equity_order"],
            {
                "account_number": "123",
                "symbol": "SPY",
                "side": "buy",
                "type": "market",
                "market_hours": "regular_hours",
                "time_in_force": "gfd",
                "dollar_amount": "10.00",
            },
        )

    def test_agentic_mcp_broker_missing_review_estimates_are_none(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": True}]},
                "review_equity_order": {"status": "approved"},
            }
        )
        broker = AgenticMcpEquityBroker("123", client)

        review = broker.review_order(OrderIntent("SPY", "buy", dollar_amount=10.0), price=100.0)

        self.assertTrue(review.approved)
        self.assertIsNone(review.estimated_price)
        self.assertIsNone(review.estimated_quantity)
        self.assertIsNone(review.estimated_cost)

    def test_agentic_mcp_broker_places_when_live_gates_enabled(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": True}]},
                "review_equity_order": {"status": "approved", "estimated_quantity": "0.1"},
                "place_equity_order": {
                    "id": "live-order",
                    "state": "submitted",
                    "quantity": "0.1",
                    "average_price": "100.0",
                },
            }
        )
        broker = AgenticMcpEquityBroker(
            "123",
            client,
            live_trading_enabled=True,
            auto_place_orders=True,
        )

        result = broker.place_order(OrderIntent("SPY", "buy", dollar_amount=10.0), price=100.0)

        self.assertTrue(result.placed)
        self.assertEqual(result.order_id, "live-order")
        self.assertIn("place_equity_order", client.calls)

    def test_agentic_mcp_broker_live_order_fuse_allows_one_submission(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": True}]},
                "review_equity_order": {"status": "approved", "estimated_quantity": "0.1"},
                "place_equity_order": {"id": "live-order", "state": "submitted"},
            }
        )
        broker = AgenticMcpEquityBroker(
            "123",
            client,
            live_trading_enabled=True,
            auto_place_orders=True,
            max_live_order_dollars=10.0,
        )

        first = broker.place_order(OrderIntent("SPY", "buy", dollar_amount=1.0), price=100.0)
        second = broker.place_order(OrderIntent("SPY", "buy", dollar_amount=1.0), price=100.0)

        self.assertTrue(first.placed)
        self.assertFalse(second.placed)
        self.assertEqual(second.status, "rejected")
        self.assertIn("live order fuse tripped", second.reason)
        self.assertEqual(client.calls.count("place_equity_order"), 1)

    def test_agentic_mcp_broker_marks_missing_order_id_as_unconfirmed(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": True}]},
                "review_equity_order": {"status": "approved", "estimated_quantity": "0.1"},
                "place_equity_order": {"state": "submitted"},
            }
        )
        broker = AgenticMcpEquityBroker(
            "123",
            client,
            live_trading_enabled=True,
            auto_place_orders=True,
            max_live_order_dollars=10.0,
        )

        result = broker.place_order(OrderIntent("SPY", "buy", dollar_amount=1.0), price=100.0)

        self.assertFalse(result.placed)
        self.assertEqual(result.status, "unconfirmed")
        self.assertIn("missing order id", result.reason)
        self.assertEqual(result.order_id, "")
        self.assertEqual(client.calls.count("place_equity_order"), 1)

    def test_agentic_mcp_broker_attempt_fuse_blocks_after_unconfirmed_submission(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": True}]},
                "review_equity_order": {"status": "approved", "estimated_quantity": "0.1"},
                "place_equity_order": {"state": "submitted"},
            }
        )
        broker = AgenticMcpEquityBroker(
            "123",
            client,
            live_trading_enabled=True,
            auto_place_orders=True,
            max_live_order_dollars=10.0,
        )

        first = broker.place_order(OrderIntent("SPY", "buy", dollar_amount=1.0), price=100.0)
        second = broker.place_order(OrderIntent("SPY", "buy", dollar_amount=1.0), price=100.0)

        self.assertEqual(first.status, "unconfirmed")
        self.assertFalse(second.placed)
        self.assertEqual(second.status, "rejected")
        self.assertIn("live order fuse tripped", second.reason)
        self.assertIn("attempted", second.reason)
        self.assertEqual(client.calls.count("place_equity_order"), 1)

    def test_agentic_mcp_broker_rejects_invalid_live_order_fuse(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": True}]},
                "review_equity_order": {"status": "approved", "estimated_quantity": "0.1"},
                "place_equity_order": {"id": "live-order", "state": "submitted"},
            }
        )
        broker = AgenticMcpEquityBroker(
            "123",
            client,
            live_trading_enabled=True,
            auto_place_orders=True,
            max_live_orders_per_process=0,
        )

        result = broker.place_order(OrderIntent("SPY", "buy", dollar_amount=1.0), price=100.0)

        self.assertFalse(result.placed)
        self.assertEqual(result.status, "rejected")
        self.assertIn("max_live_orders_per_process", result.reason)
        self.assertNotIn("place_equity_order", client.calls)

    def test_agentic_mcp_broker_rejects_live_buy_above_cap(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": True}]},
                "review_equity_order": {"status": "approved"},
                "place_equity_order": {"id": "live-order"},
            }
        )
        broker = AgenticMcpEquityBroker(
            "123",
            client,
            live_trading_enabled=True,
            auto_place_orders=True,
            max_live_order_dollars=5.0,
        )

        result = broker.place_order(OrderIntent("SPY", "buy", dollar_amount=10.0), price=100.0)

        self.assertFalse(result.placed)
        self.assertEqual(result.status, "rejected")
        self.assertIn("max_live_order_dollars", result.reason)
        self.assertNotIn("place_equity_order", client.calls)

    def test_agentic_mcp_broker_rejects_live_quantity_order_above_cap(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": True}]},
                "review_equity_order": {"status": "approved"},
                "place_equity_order": {"id": "live-order"},
            }
        )
        broker = AgenticMcpEquityBroker(
            "123",
            client,
            live_trading_enabled=True,
            auto_place_orders=True,
            max_live_order_dollars=5.0,
        )

        result = broker.place_order(OrderIntent("SPY", "sell", quantity=0.1), price=100.0)

        self.assertFalse(result.placed)
        self.assertEqual(result.status, "rejected")
        self.assertIn("max_live_order_dollars", result.reason)
        self.assertNotIn("place_equity_order", client.calls)

    def test_agentic_mcp_broker_blocks_untradable_symbol(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {"results": [{"symbol": "SPY", "tradable": False}]},
                "review_equity_order": {"status": "approved"},
            }
        )
        broker = AgenticMcpEquityBroker("123", client)

        review = broker.review_order(OrderIntent("SPY", "buy", dollar_amount=10.0), price=100.0)

        self.assertFalse(review.approved)
        self.assertIn("tradable=false", review.alerts[0])
        self.assertNotIn("review_equity_order", client.calls)

    def test_streamable_http_mcp_client_reads_bearer_token_from_env(self):
        old_value = os.environ.get("RH_MCP_TOKEN")
        os.environ["RH_MCP_TOKEN"] = "secret"
        try:
            client = StreamableHttpMcpToolClient(
                "https://agent.robinhood.com/mcp/trading",
                bearer_token_env_var="RH_MCP_TOKEN",
            )
            headers = client._headers()
        finally:
            if old_value is None:
                os.environ.pop("RH_MCP_TOKEN", None)
            else:
                os.environ["RH_MCP_TOKEN"] = old_value

        self.assertEqual(headers["Authorization"], "Bearer secret")

    def test_streamable_http_mcp_client_prefers_bearer_token_over_oauth(self):
        client = StreamableHttpMcpToolClient(
            "https://agent.robinhood.com/mcp/trading",
            bearer_token="secret",
            oauth_token_store_path="R:/service/rh_agentic_mcp_tokens.json",
        )

        self.assertIsNone(client._oauth_auth())

    def test_json_token_storage_handles_missing_and_invalid_files(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "tokens.json"
            storage = JsonTokenStorage(path)

            self.assertFalse(storage.has_tokens())
            path.write_text("not json", encoding="utf-8")

            self.assertFalse(storage.has_tokens())

    def test_decode_mcp_tool_result_reads_json_text_content(self):
        class TextContent:
            text = '{"buying_power": "100.00"}'

        class Result:
            content = [TextContent()]

        decoded = decode_mcp_tool_result(Result())

        self.assertEqual(decoded["buying_power"], "100.00")

    def test_decode_mcp_tools_result_normalizes_sdk_shapes(self):
        class Tool:
            name = "get_equity_orders"
            description = "List equity orders."
            inputSchema = {"type": "object"}

        class Result:
            tools = [Tool(), {"name": "get_order", "input_schema": {"type": "object"}}]

        decoded = decode_mcp_tools_result(Result())

        self.assertEqual(decoded[0]["name"], "get_equity_orders")
        self.assertEqual(decoded[0]["input_schema"], {"type": "object"})
        self.assertEqual(decoded[1]["name"], "get_order")

    def test_mcp_orders_arguments_and_summary_are_stable(self):
        args = build_parser().parse_args(["mcp-orders", "--symbol", "spy", "--state", "queued"])

        self.assertEqual(
            _mcp_orders_arguments("123", args),
            {"account_number": "123", "symbol": "SPY", "state": "queued"},
        )

        rows = _extract_order_rows(
            {
                "data": {
                    "orders": [
                        {
                            "id": "order-1",
                            "symbol": "SPY",
                            "side": "buy",
                            "type": "market",
                            "state": "queued",
                            "dollar_based_amount": {"amount": "1.00"},
                            "filled_quantity": "0",
                            "created_at": "2026-06-28T15:33:39Z",
                        }
                    ]
                }
            }
        )
        summary = _format_order_row(rows[0])

        self.assertEqual(len(rows), 1)
        self.assertIn("SPY buy market state=queued", summary)
        self.assertIn("dollars=1.00", summary)
        self.assertIn("id=order-1", summary)

    def test_reconcile_order_result_recovers_missing_order_id(self):
        client = _FakeMcpClient(
            {
                "get_equity_orders": {
                    "data": {
                        "orders": [
                            {
                                "id": "order-1",
                                "symbol": "SPY",
                                "side": "buy",
                                "type": "market",
                                "state": "queued",
                                "dollar_based_amount": {"amount": "1.00"},
                                "cumulative_quantity": "0.000000",
                            }
                        ]
                    }
                }
            }
        )
        result = OrderResult(
            intent=OrderIntent("SPY", "buy", dollar_amount=1.0),
            placed=True,
            status="submitted",
            reason="mcp order submitted",
        )

        reconciled = _reconcile_order_result("123", client, result)

        self.assertEqual(reconciled.order_id, "order-1")
        self.assertEqual(reconciled.status, "queued")
        self.assertEqual(reconciled.filled_quantity, 0.0)
        self.assertIn("reconciled_order", reconciled.raw)

    def test_reconcile_order_result_promotes_unconfirmed_order(self):
        client = _FakeMcpClient(
            {
                "get_equity_orders": {
                    "data": {
                        "orders": [
                            {
                                "id": "order-1",
                                "symbol": "SPY",
                                "side": "buy",
                                "type": "market",
                                "state": "queued",
                                "dollar_based_amount": {"amount": "1.00"},
                            }
                        ]
                    }
                }
            }
        )
        result = OrderResult(
            intent=OrderIntent("SPY", "buy", dollar_amount=1.0),
            placed=False,
            status="unconfirmed",
            reason="mcp order submission unconfirmed: missing order id",
        )

        reconciled = _reconcile_order_result("123", client, result)

        self.assertTrue(reconciled.placed)
        self.assertEqual(reconciled.order_id, "order-1")
        self.assertEqual(reconciled.status, "queued")

    def test_reconcile_journal_rows_appends_status_event(self):
        client = _FakeMcpClient(
            {
                "get_equity_orders": {
                    "data": {
                        "orders": [
                            {
                                "id": "order-1",
                                "symbol": "SPY",
                                "side": "buy",
                                "type": "market",
                                "state": "filled",
                                "dollar_based_amount": {"amount": "1.00"},
                                "cumulative_quantity": "0.001",
                                "average_price": "100.00",
                                "placed_agent": "agentic",
                            }
                        ]
                    }
                }
            }
        )
        rows = [
            {
                "timestamp": "2026-06-28T15:33:39+00:00",
                "event_type": "broker_execution",
                "dry_run": False,
                "symbol": "SPY",
                "action": "BUY",
                "execution": {
                    "placed": True,
                    "order_id": "",
                    "order_intent": {
                        "symbol": "SPY",
                        "side": "buy",
                        "type": "market",
                        "dollar_amount": 1.0,
                        "quantity": None,
                        "limit_price": None,
                    },
                },
            }
        ]

        events = _reconcile_journal_rows("123", client, rows)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "broker_reconciliation")
        self.assertEqual(events[0]["order_id"], "order-1")
        self.assertEqual(events[0]["broker_status"], "filled")

    def test_bot_writes_journal_entry(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgenticConfig(symbols=SymbolConfig(stocks=("AAPL",)))
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            bot = AgenticBot(config=config, journal=DecisionJournal(journal_path))

            entry = bot.analyze(QuoteSnapshot("AAPL", price=102.0, previous_close=100.0))

            self.assertEqual(entry.decision["action"], "BUY")
            rows = journal_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(rows), 1)
        payload = json.loads(rows[0])
        self.assertEqual(payload["decision"]["symbol"], "AAPL")
        self.assertTrue(payload["dry_run"])

    def test_json_quote_provider_reads_symbol_quote(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            quote_path = Path(tmp_dir) / "quotes.json"
            quote_path.write_text(
                json.dumps({"symbols": {"AAPL": {"price": 205, "previous_close": 200}}}),
                encoding="utf-8",
            )

            quote = JsonQuoteProvider(quote_path).get_quote("aapl")

        self.assertEqual(quote.symbol, "AAPL")
        self.assertEqual(quote.price, 205.0)
        self.assertEqual(quote.previous_close, 200.0)

    def test_json_quote_provider_creates_missing_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            quote_path = Path(tmp_dir) / "quotes.json"

            provider = JsonQuoteProvider(quote_path)

            self.assertTrue(quote_path.exists())
            self.assertEqual(quote_path.read_text(encoding="utf-8"), "{}")
            with self.assertRaises(QuoteUnavailable):
                provider.get_quote("AAPL")

    def test_json_quote_provider_reports_missing_symbol(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            quote_path = Path(tmp_dir) / "quotes.json"
            quote_path.write_text(
                json.dumps({"symbols": {"AAPL": {"price": 205, "previous_close": 200}}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(QuoteUnavailable, "MSFT"):
                JsonQuoteProvider(quote_path).get_quote("MSFT")

    def test_paper_session_runs_one_iteration(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            quote_path = Path(tmp_dir) / "quotes.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            quote_path.write_text(
                json.dumps({"AAPL": {"price": 102, "previous_close": 100}}),
                encoding="utf-8",
            )
            config = AgenticConfig(
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("AAPL",)),
                paper_starting_cash=100.0,
            )
            session = PaperSession(
                config=config,
                quote_provider=JsonQuoteProvider(quote_path),
                paper_account=PaperAccount(cash=100.0),
                show_progress=False,
            )

            result = session.run(max_iterations=1)

        self.assertEqual(result.iterations, 1)
        self.assertEqual(result.decisions, 1)
        self.assertEqual(result.skipped_quotes, 0)
        self.assertEqual(result.collection_errors, 0)
        self.assertLess(result.paper_cash, 100.0)
        self.assertIn("AAPL", result.positions)

    def test_broker_session_reviews_approved_trade(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            quote_path = Path(tmp_dir) / "quotes.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            quote_path.write_text(
                json.dumps({"AAPL": {"price": 102, "previous_close": 100}}),
                encoding="utf-8",
            )
            config = AgenticConfig(
                broker="agentic_mcp",
                dry_run=True,
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("AAPL",)),
                paper_starting_cash=100.0,
            )
            broker = _FakeReviewBroker(cash=100.0)
            session = BrokerSession(
                config=config,
                quote_provider=JsonQuoteProvider(quote_path),
                broker=broker,
                show_progress=False,
            )

            result = session.run(max_iterations=1)
            rows = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result.decisions, 1)
        self.assertEqual(result.paper_cash, 100.0)
        self.assertEqual(len(broker.orders), 1)
        self.assertEqual(broker.orders[0].symbol, "AAPL")
        self.assertEqual(broker.orders[0].side, "buy")
        self.assertEqual(broker.orders[0].dollar_amount, 10.0)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["event_type"], "broker_execution")
        self.assertEqual(rows[1]["decision_timestamp"], rows[0]["timestamp"])
        self.assertEqual(rows[1]["execution"]["broker_status"], "reviewed")
        self.assertEqual(rows[1]["execution"]["broker_reason"], "live order placement disabled")
        self.assertFalse(rows[1]["execution"]["placed"])
        self.assertEqual(rows[1]["execution"]["order_intent"]["symbol"], "AAPL")
        self.assertEqual(rows[1]["execution"]["order_intent"]["dollar_amount"], 10.0)

    def test_broker_session_journals_plan_rejection(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            quote_path = Path(tmp_dir) / "quotes.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            quote_path.write_text(
                json.dumps({"AAPL": {"price": 102, "previous_close": 100}}),
                encoding="utf-8",
            )
            config = AgenticConfig(
                broker="agentic_mcp",
                dry_run=True,
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("AAPL",)),
                risk=RiskConfig(min_cash_reserve=100.0),
            )
            broker = _FakeReviewBroker(cash=100.0)
            session = BrokerSession(
                config=config,
                quote_provider=JsonQuoteProvider(quote_path),
                broker=broker,
                show_progress=False,
            )

            session.run(max_iterations=1)
            rows = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(broker.orders), 0)
        self.assertEqual(rows[1]["event_type"], "broker_execution")
        self.assertEqual(rows[1]["execution"]["broker_status"], "planned_rejected")
        self.assertEqual(rows[1]["execution"]["broker_reason"], "available dollars below minimum order size")
        self.assertIsNone(rows[1]["execution"]["order_intent"])

    def test_daily_candle_broker_session_reviews_daily_trend_trade(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "candles.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            candles = tuple(_daily_candles("SPY", [100 + index for index in range(60)]))
            config = AgenticConfig(
                broker="agentic_mcp",
                dry_run=True,
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("SPY",)),
                lanes=(
                    LaneConfig(
                        "stocks",
                        symbols=("SPY",),
                        strategy="daily_trend_follow",
                        poll_seconds=86400,
                    ),
                ),
                risk=RiskConfig(max_trade_dollars=10.0, min_cash_reserve=50.0),
            )
            broker = _FakeReviewBroker(cash=100.0)
            session = DailyCandleBrokerSession(
                config=config,
                candle_collector=CandleCollector(
                    source=StaticHistoricalMarketDataSource({"SPY": candles}),
                    cache_path=cache_path,
                ),
                broker=broker,
            )

            result = session.run_once()
            rows = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result.iterations, 1)
        self.assertEqual(result.decisions, 1)
        self.assertEqual(result.collection_errors, 0)
        self.assertEqual(len(broker.orders), 1)
        self.assertEqual(broker.orders[0].symbol, "SPY")
        self.assertEqual(broker.orders[0].side, "buy")
        self.assertEqual(broker.orders[0].dollar_amount, 10.0)
        self.assertEqual(rows[0]["decision"]["action"], "BUY")
        self.assertEqual(rows[1]["event_type"], "broker_execution")
        self.assertEqual(rows[1]["execution"]["broker_status"], "reviewed")

    def test_daily_candle_broker_session_reconciles_placed_order_before_journal(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "candles.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            candles = tuple(_daily_candles("SPY", [100 + index for index in range(60)]))
            config = AgenticConfig(
                broker="agentic_mcp",
                dry_run=False,
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("SPY",)),
                lanes=(LaneConfig("stocks", symbols=("SPY",), strategy="daily_trend_follow"),),
                risk=RiskConfig(max_trade_dollars=5.0),
            )
            broker = _FakePlacedBroker(cash=100.0)

            def reconcile(result):
                return OrderResult(
                    intent=result.intent,
                    placed=result.placed,
                    status="queued",
                    reason=result.reason,
                    order_id="reconciled-1",
                    filled_quantity=result.filled_quantity,
                    average_price=result.average_price,
                    raw=result.raw,
                )

            session = DailyCandleBrokerSession(
                config=config,
                candle_collector=CandleCollector(
                    source=StaticHistoricalMarketDataSource({"SPY": candles}),
                    cache_path=cache_path,
                ),
                broker=broker,
                order_result_reconciler=reconcile,
            )

            session.run_once()
            rows = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(rows[1]["execution"]["broker_status"], "queued")
        self.assertEqual(rows[1]["execution"]["order_id"], "reconciled-1")
        self.assertEqual(rows[1]["execution"]["order_intent"]["dollar_amount"], 5.0)

    def test_daily_candle_broker_session_prints_portfolio_plan_summary(self):
        import contextlib
        import io
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "candles.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            config = AgenticConfig(
                broker="agentic_mcp",
                dry_run=True,
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("SPY", "QQQ")),
                lanes=(
                    LaneConfig(
                        "stocks",
                        symbols=("SPY", "QQQ"),
                        strategy="daily_trend_follow",
                        poll_seconds=86400,
                    ),
                ),
                risk=RiskConfig(max_open_positions=1, max_trade_dollars=10.0),
            )
            broker = _FakeReviewBroker(
                cash=100.0,
                positions={"SPY": Position("SPY", quantity=0.001, average_cost=100.0)},
            )
            session = DailyCandleBrokerSession(
                config=config,
                candle_collector=CandleCollector(
                    source=StaticHistoricalMarketDataSource(
                        {
                            "SPY": tuple(_daily_candles("SPY", [100] * 60)),
                            "QQQ": tuple(_daily_candles("QQQ", [100 + index for index in range(60)])),
                        }
                    ),
                    cache_path=cache_path,
                ),
                broker=broker,
            )
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                session.run_once()

        self.assertIn(
            "[daily-plan] open_positions=SPY buy_signals=QQQ ranked_buys=QQQ:",
            output.getvalue(),
        )
        self.assertIn(
            "top_buy=QQQ sell_signals=- blocked=QQQ:max open positions reached selected=HOLD",
            output.getvalue(),
        )

    def test_daily_plan_summary_ranks_buys_by_trend_metrics(self):
        summary = _daily_plan_summary_line(
            (),
            [
                DailyPlanItem(
                    "IWM",
                    "BUY",
                    1.0,
                    "daily trend entry close=10.00 ema20=9.90 ema50=9.50 trend=4.20% atr=1.00%",
                    True,
                    "approved",
                    "no broker order: max open positions reached",
                ),
                DailyPlanItem(
                    "QQQ",
                    "BUY",
                    1.0,
                    "daily trend entry close=10.00 ema20=9.90 ema50=9.50 trend=6.10% atr=2.00%",
                    True,
                    "approved",
                    "no broker order: max open positions reached",
                ),
                DailyPlanItem(
                    "TLT",
                    "BUY",
                    1.0,
                    "daily trend entry close=10.00 ema20=9.90 ema50=9.50 trend=6.10% atr=1.50%",
                    True,
                    "approved",
                    "no broker order: max open positions reached",
                ),
            ],
        )

        self.assertIn("buy_signals=TLT,QQQ,IWM", summary)
        self.assertIn(
            "ranked_buys=TLT:trend=6.10/atr=1.50,QQQ:trend=6.10/atr=2.00,IWM:trend=4.20/atr=1.00",
            summary,
        )
        self.assertIn("top_buy=TLT", summary)

    def test_daily_plan_summary_falls_back_to_confidence(self):
        summary = _daily_plan_summary_line(
            (),
            [
                DailyPlanItem(
                    "IWM", "BUY", 0.40, "fallback", True, "approved", "no broker order: max open positions reached"
                ),
                DailyPlanItem(
                    "QQQ", "BUY", 0.75, "fallback", True, "approved", "no broker order: max open positions reached"
                ),
            ],
        )

        self.assertIn("buy_signals=QQQ,IWM", summary)
        self.assertIn("ranked_buys=QQQ:confidence=0.75,IWM:confidence=0.40", summary)

    def test_paper_session_skips_missing_quote_symbol(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            quote_path = Path(tmp_dir) / "quotes.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            quote_path.write_text(
                json.dumps({"AAPL": {"price": 102, "previous_close": 100}}),
                encoding="utf-8",
            )
            config = AgenticConfig(
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("AAPL", "MSFT")),
                paper_starting_cash=100.0,
            )
            session = PaperSession(config=config, quote_provider=JsonQuoteProvider(quote_path))

            result = session.run(max_iterations=1)

        self.assertEqual(result.iterations, 1)
        self.assertEqual(result.decisions, 1)
        self.assertEqual(result.skipped_quotes, 1)

    def test_quote_collector_writes_cache(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "quotes.json"
            collector = QuoteCollector(
                source=StaticMarketDataSource({"AAPL": QuoteSnapshot("AAPL", price=102, previous_close=100)}),
                cache_path=cache_path,
            )

            quotes, errors = collector.collect(["AAPL"])
            payload = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(errors, {})
        self.assertIn("AAPL", quotes)
        self.assertEqual(payload["symbols"]["AAPL"]["price"], 102)

    def test_candle_collector_writes_cache(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "candles.json"
            candles = tuple(_daily_candles("SPY", [100, 101, 102]))
            collector = CandleCollector(
                source=StaticHistoricalMarketDataSource({"SPY": candles}),
                cache_path=cache_path,
            )

            collected, errors = collector.collect(["SPY"])
            payload = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(errors, {})
        self.assertEqual(len(collected["SPY"]), 3)
        self.assertEqual(payload["symbols"]["SPY"][-1]["close"], 102)

    def test_daily_trend_backtest_records_buy_and_open_value(self):
        strategy = DailyTrendFollowStrategy(
            short_period=3,
            long_period=5,
            atr_period=3,
            min_trend_pct=0.01,
            target_dollars=10.0,
        )

        result = run_daily_trend_backtest(
            "SPY",
            _daily_candles("SPY", [100, 101, 102, 103, 104, 105]),
            starting_cash=100.0,
            target_dollars=10.0,
            min_cash_reserve=50.0,
            slippage_pct=0.0,
            strategy=strategy,
        )

        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].side, "BUY")
        self.assertAlmostEqual(result.ending_cash, 90.0)
        self.assertGreater(result.ending_value, 99.0)
        self.assertEqual(len(result.equity_curve), 6)

    def test_daily_trend_backtest_records_sell_after_breakdown(self):
        strategy = DailyTrendFollowStrategy(
            short_period=3,
            long_period=5,
            atr_period=3,
            min_trend_pct=0.01,
            target_dollars=10.0,
        )

        result = run_daily_trend_backtest(
            "SPY",
            _daily_candles("SPY", [100, 101, 102, 103, 104, 105, 95]),
            starting_cash=100.0,
            target_dollars=10.0,
            min_cash_reserve=50.0,
            slippage_pct=0.0,
            strategy=strategy,
        )

        self.assertEqual(tuple(trade.side for trade in result.trades), ("BUY", "SELL"))
        self.assertLess(result.ending_value, 100.0)
        self.assertLess(result.max_drawdown_pct, 0.0)

    def test_daily_trend_backtest_respects_cash_reserve(self):
        strategy = DailyTrendFollowStrategy(
            short_period=3,
            long_period=5,
            atr_period=3,
            min_trend_pct=0.01,
            target_dollars=10.0,
        )

        result = run_daily_trend_backtest(
            "SPY",
            _daily_candles("SPY", [100, 101, 102, 103, 104, 105]),
            starting_cash=55.0,
            target_dollars=10.0,
            min_cash_reserve=50.0,
            slippage_pct=0.0,
            strategy=strategy,
        )

        self.assertEqual(len(result.trades), 1)
        self.assertAlmostEqual(result.trades[0].dollars, 5.0)
        self.assertAlmostEqual(result.ending_cash, 50.0)

    def test_daily_trend_portfolio_backtest_limits_new_buys_per_day(self):
        candles = {
            "SPY": tuple(_daily_candles("SPY", [100 + index for index in range(60)])),
            "QQQ": tuple(_daily_candles("QQQ", [200 + index for index in range(60)])),
        }

        result = run_daily_trend_portfolio_backtest(
            candles,
            starting_cash=100.0,
            target_dollars=10.0,
            min_cash_reserve=50.0,
            max_open_positions=2,
            max_new_buys_per_day=1,
            max_daily_trades=2,
            max_total_exposure_dollars=50.0,
            slippage_pct=0.0,
        )

        self.assertEqual(len(result.trades), 2)
        self.assertEqual(tuple(trade.side for trade in result.trades), ("BUY", "BUY"))
        self.assertNotEqual(result.trades[0].date, result.trades[1].date)
        self.assertAlmostEqual(result.ending_cash, 80.0)

    def test_daily_trend_portfolio_backtest_limits_open_positions(self):
        candles = {
            "SPY": tuple(_daily_candles("SPY", [100 + index for index in range(60)])),
            "QQQ": tuple(_daily_candles("QQQ", [200 + index for index in range(60)])),
            "IWM": tuple(_daily_candles("IWM", [50 + index for index in range(60)])),
        }

        result = run_daily_trend_portfolio_backtest(
            candles,
            starting_cash=100.0,
            target_dollars=10.0,
            min_cash_reserve=50.0,
            max_open_positions=2,
            max_new_buys_per_day=3,
            max_daily_trades=3,
            max_total_exposure_dollars=50.0,
            slippage_pct=0.0,
        )

        buy_trades = [trade for trade in result.trades if trade.side == "BUY"]
        self.assertEqual(len(buy_trades), 2)
        self.assertAlmostEqual(result.ending_cash, 80.0)

    def test_paper_session_collects_quotes_before_decision(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "quotes.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            config = AgenticConfig(
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("AAPL",)),
                lanes=(LaneConfig("stocks", symbols=("AAPL",), poll_seconds=60),),
                paper_starting_cash=100.0,
            )
            session = PaperSession(
                config=config,
                quote_provider=JsonQuoteProvider(cache_path),
                quote_collector=QuoteCollector(
                    source=StaticMarketDataSource({"AAPL": QuoteSnapshot("AAPL", price=102, previous_close=100)}),
                    cache_path=cache_path,
                ),
                show_progress=False,
            )

            result = session.run(max_iterations=1)

        self.assertEqual(result.decisions, 1)
        self.assertEqual(result.collection_errors, 0)
        self.assertLess(result.paper_cash, 100.0)

    def test_paper_session_counts_collection_errors_once(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "quotes.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            config = AgenticConfig(
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("AAPL",)),
                lanes=(LaneConfig("stocks", symbols=("AAPL",), poll_seconds=60),),
            )
            session = PaperSession(
                config=config,
                quote_provider=JsonQuoteProvider(cache_path),
                quote_collector=QuoteCollector(
                    source=StaticMarketDataSource({}),
                    cache_path=cache_path,
                ),
                show_progress=False,
            )

            result = session.run(max_iterations=1)

        self.assertEqual(result.decisions, 0)
        self.assertEqual(result.collection_errors, 1)
        self.assertEqual(result.skipped_quotes, 0)

    def test_paper_session_enforces_daily_trade_limit(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            quote_path = Path(tmp_dir) / "quotes.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            quote_path.write_text(
                json.dumps(
                    {
                        "AAPL": {"price": 102, "previous_close": 100},
                        "MSFT": {"price": 204, "previous_close": 200},
                    }
                ),
                encoding="utf-8",
            )
            config = AgenticConfig(
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("AAPL", "MSFT")),
                risk=RiskConfig(max_daily_trades=1),
                paper_starting_cash=100.0,
            )
            session = PaperSession(
                config=config,
                quote_provider=JsonQuoteProvider(quote_path),
                paper_account=PaperAccount(cash=100.0),
                show_progress=False,
            )

            result = session.run(max_iterations=1)
            rows = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result.decisions, 2)
        self.assertAlmostEqual(result.paper_cash, 90.0)
        self.assertEqual(rows[0]["risk"]["reason"], "approved for dry-run review")
        self.assertFalse(rows[1]["risk"]["approved"])
        self.assertEqual(rows[1]["risk"]["reason"], "daily trade limit reached")

    def test_session_reports_next_due_lane_names(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgenticConfig()
            session = PaperSession(
                config=config,
                quote_provider=JsonQuoteProvider(Path(tmp_dir) / "unused_quotes.json"),
                show_progress=False,
            )
            session._lane_next_run = {"stocks": 10.0, "scalps": 5.0, "crypto": 5.0}

            self.assertEqual(session._next_due_lane_names(), ("scalps", "crypto"))

    def test_paper_session_handles_keyboard_interrupt(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "quotes.json"
            journal_path = Path(tmp_dir) / "decisions.jsonl"
            config = AgenticConfig(
                journal_path=str(journal_path),
                symbols=SymbolConfig(stocks=("AAPL",)),
                lanes=(LaneConfig("stocks", symbols=("AAPL",), poll_seconds=60),),
            )
            session = PaperSession(
                config=config,
                quote_provider=JsonQuoteProvider(cache_path),
                quote_collector=QuoteCollector(
                    source=StaticMarketDataSource({"AAPL": QuoteSnapshot("AAPL", price=102, previous_close=100)}),
                    cache_path=cache_path,
                ),
                show_progress=False,
            )

            with patch.object(session, "_sleep_until_next_poll", side_effect=KeyboardInterrupt):
                result = session.run()

        self.assertTrue(result.interrupted)
        self.assertEqual(result.iterations, 1)
        self.assertEqual(result.decisions, 1)


def _daily_candles(symbol, closes):
    from datetime import date, timedelta

    start = date(2026, 1, 1)
    return [
        Candle(
            symbol=symbol,
            date=start + timedelta(days=index),
            open=close - 0.25,
            high=close + 0.5,
            low=close - 0.5,
            close=close,
            volume=1000000,
        )
        for index, close in enumerate(closes)
    ]


class _FakeMcpClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.call_arguments = {}

    def call_tool(self, name, arguments):
        self.calls.append(name)
        self.call_arguments[name] = arguments
        return self.responses.get(name, {})


class _FakeReviewBroker:
    def __init__(self, cash=100.0, positions=None):
        self.cash = cash
        self.positions = dict(positions or {})
        self.orders = []

    def get_account_snapshot(self):
        return AccountSnapshot(cash=self.cash, positions=dict(self.positions))

    def review_order(self, intent, price):
        raise AssertionError("BrokerSession should call place_order for approved intents")

    def place_order(self, intent, price):
        self.orders.append(intent)
        return OrderResult(
            intent=intent,
            placed=False,
            status="reviewed",
            reason="live order placement disabled",
        )


class _FakePlacedBroker(_FakeReviewBroker):
    def place_order(self, intent, price):
        self.orders.append(intent)
        return OrderResult(
            intent=intent,
            placed=True,
            status="submitted",
            reason="mcp order submitted",
            order_id="",
        )


class _FakeConfirmedBroker(_FakeReviewBroker):
    def place_order(self, intent, price):
        self.orders.append(intent)
        return OrderResult(
            intent=intent,
            placed=True,
            status="submitted",
            reason="mcp order submitted",
            order_id=f"order-{len(self.orders)}",
        )


if __name__ == "__main__":
    unittest.main()
