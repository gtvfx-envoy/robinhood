"""Command-line entry point for the agentic dry-run bot."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from .bot import AgenticBot
from .config import get_personal_config_path, load_config
from .market_data import QuoteCollector, YahooChartMarketDataSource
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

    quote = ManualQuoteProvider(args.price, args.previous_close).get_quote(args.symbol.strip().upper())
    entry = bot.analyze(quote)

    decision = entry.decision
    risk = entry.risk
    print(f"{decision['symbol']}: {decision['action']}")
    print(f"Reason: {decision['reason']}")
    print(f"Risk: {risk['reason']}")
    print("No order submitted: dry-run mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
