import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from robinhood.agentic.backtest import run_daily_trend_backtest, run_daily_trend_portfolio_backtest
from robinhood.agentic.broker import OrderIntent, PaperBroker
from robinhood.agentic.bot import AgenticBot
from robinhood.agentic.config import (
    AgenticConfig,
    LaneConfig,
    RiskConfig,
    SymbolConfig,
    get_personal_config_path,
    load_lanes,
    load_config,
    load_personal_config,
    load_symbols,
)
from robinhood.agentic.execution import plan_order_intent
from robinhood.agentic.journal import DecisionJournal
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
)
from robinhood.agentic.paper import PaperAccount
from robinhood.agentic.quotes import JsonQuoteProvider, QuoteUnavailable
from robinhood.agentic.risk import RiskManager
from robinhood.agentic.session import PaperSession
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
                        "journal_path": "R:/service/agentic_decisions.jsonl",
                        "quote_source_path": "R:/service/rh_quotes.json",
                        "poll_seconds": 30,
                        "paper_starting_cash": 5000,
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
        self.assertEqual(config.journal_path, "R:/service/agentic_decisions.jsonl")
        self.assertEqual(config.quote_source_path, "R:/service/rh_quotes.json")
        self.assertEqual(config.poll_seconds, 30.0)
        self.assertEqual(config.paper_starting_cash, 5000.0)

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
                "get_equity_positions": {
                    "results": [
                        {"symbol": "SPY", "quantity": "0.1", "average_cost": "100.0"}
                    ]
                },
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
                    "data": {
                        "positions": [
                            {"symbol": "SPY", "quantity": "0.1", "average_cost": "100.0"}
                        ]
                    },
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

    def test_agentic_mcp_broker_blocks_untradable_symbol(self):
        client = _FakeMcpClient(
            {
                "get_equity_tradability": {
                    "results": [{"symbol": "SPY", "tradable": False}]
                },
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
                source=StaticMarketDataSource(
                    {"AAPL": QuoteSnapshot("AAPL", price=102, previous_close=100)}
                ),
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
                    source=StaticMarketDataSource(
                        {"AAPL": QuoteSnapshot("AAPL", price=102, previous_close=100)}
                    ),
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
            rows = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]

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
                    source=StaticMarketDataSource(
                        {"AAPL": QuoteSnapshot("AAPL", price=102, previous_close=100)}
                    ),
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


if __name__ == "__main__":
    unittest.main()
