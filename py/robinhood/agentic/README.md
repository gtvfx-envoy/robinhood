# Agentic Technical Notes

This package contains the local agentic trading scaffold. It is intentionally
dry-run and paper-trading first. Live order review and placement should be added
behind explicit confirmation boundaries.

## Architecture

The long-running bot is a single process with four stages:

1. Scheduler selects due lanes.
2. Collector fetches quote snapshots and updates the quote cache.
3. Decision stage dispatches lane symbols to the configured strategy.
4. Executor applies the decision. The current executor is paper trading only.

## Configuration

Tracked config:

- `config/symbols.cfg`: lane definitions.

Personal config:

- Resolved from `SERVICE_ROOT\rh_agentic.json`.
- The filename is fixed as `rh_agentic.json`.
- Account number, local paths, risk limits, polling cadence, and paper cash stay
  outside git.

Example personal config:

```json
{
  "account_number": "551641152",
  "dry_run": true,
  "journal_path": "R:/service/rh_agentic_decisions.jsonl",
  "quote_source_path": "R:/service/rh_quotes.json",
  "poll_seconds": 60.0,
  "paper_starting_cash": 10000.0,
  "risk": {
    "max_trade_dollars": 25.0,
    "max_daily_trades": 3,
    "allow_shorts": false,
    "allow_options": false
  }
}
```

## Quote Providers

`MarketDataSource` abstracts fresh quote collection. `QuoteProvider` abstracts
reading quote snapshots from cache/fallback sources.

Current providers:

- `YahooChartMarketDataSource`: dependency-free HTTP quote source used by
  default in `run`.
- `ManualQuoteProvider`: one-shot tests and CLI smoke checks.
- `JsonQuoteProvider`: persistent sessions read quotes from a JSON file produced
  by the collector/cache writer.

`JsonQuoteProvider` creates a missing quote file with `{}` so first-run startup
does not fail. Missing symbols, invalid JSON, invalid shape, and invalid numeric
fields are reported as `QuoteUnavailable`.

Supported quote file shapes:

```json
{
  "symbols": {
    "AAPL": {
      "price": 205.0,
      "previous_close": 200.0
    }
  }
}
```

or:

```json
{
  "AAPL": {
    "price": 205.0,
    "previous_close": 200.0
  }
}
```

## Session Loop

`PaperSession` runs the persistent loop:

1. Find lanes whose `poll_seconds` interval has elapsed.
2. Collect quotes for each lane and write the JSON quote cache.
3. Fall back to the cache when collection does not return a fresh quote.
4. Skip symbols whose quote is currently unavailable.
5. Run `AgenticBot.analyze()` with the lane's configured strategy.
6. Append a JSONL decision journal entry.
7. Apply approved decisions to `PaperAccount`.
8. Sleep until the next lane is due.

Each lane controls its own polling cadence in `config/symbols.cfg`.
The session prints lane poll summaries and a countdown progress bar by default.
`show_progress=False` or CLI `--quiet` disables the countdown while preserving
poll and decision lines.

## CLI

One-shot analysis:

```powershell
$env:SERVICE_ROOT='R:\service'
python -m robinhood.agentic.cli analyze --symbol AAPL --price 205 --previous-close 200
```

Persistent paper session:

```powershell
$env:SERVICE_ROOT='R:\service'
python -m robinhood.agentic.cli run
```

Cache-only run:

```powershell
python -m robinhood.agentic.cli run --no-collect
```

Disable countdown progress:

```powershell
python -m robinhood.agentic.cli run --quiet
```

The `run` command requires either `quote_source_path` in personal config or a
CLI override:

```powershell
python -m robinhood.agentic.cli run --quote-file R:\service\rh_quotes.json
```

## Test

```powershell
cd C:\repo\gtvfx\robinhood\py
python -m unittest discover -s tests -p test_agentic.py
```
