# Agentic Technical Notes

This package contains the local agentic trading scaffold. It is intentionally
dry-run and paper-trading first. Live order review and placement should be added
behind explicit confirmation boundaries.

## Configuration

Tracked config:

- `config/symbols.cfg`: allowed stock and crypto symbols.

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

`QuoteProvider` abstracts market data collection from strategy execution.

Current providers:

- `ManualQuoteProvider`: one-shot tests and CLI smoke checks.
- `JsonQuoteProvider`: persistent sessions read quotes from a JSON file produced
  by a separate quote collector.

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

1. Load configured stock symbols.
2. Poll `QuoteProvider` for each symbol.
3. Run `AgenticBot.analyze()`.
4. Append a JSONL decision journal entry.
5. Apply approved decisions to `PaperAccount`.
6. Sleep `poll_seconds`.

The default poll cadence is loaded from personal config. The current service
config uses `60.0` seconds.

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
