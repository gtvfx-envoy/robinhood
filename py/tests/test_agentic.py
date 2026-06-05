import json
import os
from pathlib import Path
import unittest

from robinhood.agentic.bot import AgenticBot
from robinhood.agentic.config import (
    AgenticConfig,
    RiskConfig,
    SymbolConfig,
    get_personal_config_path,
    load_config,
    load_personal_config,
    load_symbols,
)
from robinhood.agentic.journal import DecisionJournal
from robinhood.agentic.paper import PaperAccount
from robinhood.agentic.quotes import JsonQuoteProvider
from robinhood.agentic.risk import RiskManager
from robinhood.agentic.session import PaperSession
from robinhood.agentic.strategy import Decision, QuoteSnapshot, SimpleMomentumStrategy


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

    def test_load_personal_config_supports_service_file_shape(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "rh_agentic.json"
            config_path.write_text(
                json.dumps(
                    {
                        "account_number": "123456789",
                        "dry_run": True,
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
        self.assertTrue(config.dry_run)
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
                        "dry_run": True,
                        "risk": {"max_trade_dollars": 7, "max_daily_trades": 2},
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(symbols_path, personal_path)

        self.assertEqual(config.account_number, "123456789")
        self.assertEqual(config.symbols.stocks, ("AAPL",))
        self.assertEqual(config.risk.max_trade_dollars, 7.0)
        self.assertEqual(config.risk.max_daily_trades, 2)

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

    def test_risk_rejects_unlisted_symbol(self):
        config = AgenticConfig(symbols=SymbolConfig(stocks=("AAPL",)))
        manager = RiskManager(config)

        result = manager.evaluate(Decision("TSLA", "BUY", 1.0, "test", target_dollars=5.0))

        self.assertFalse(result.approved)
        self.assertIn("not in allowed", result.reason)

    def test_risk_rejects_trade_size_above_limit(self):
        config = AgenticConfig(
            symbols=SymbolConfig(stocks=("AAPL",)),
            risk=RiskConfig(max_trade_dollars=5.0),
        )
        manager = RiskManager(config)

        result = manager.evaluate(Decision("AAPL", "BUY", 1.0, "test", target_dollars=10.0))

        self.assertFalse(result.approved)
        self.assertIn("max trade size", result.reason)

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
            )

            result = session.run(max_iterations=1)

        self.assertEqual(result.iterations, 1)
        self.assertEqual(result.decisions, 1)
        self.assertLess(result.paper_cash, 100.0)
        self.assertIn("AAPL", result.positions)


if __name__ == "__main__":
    unittest.main()
