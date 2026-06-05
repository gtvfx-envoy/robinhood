# Agentic Bot User Guide

This bot is currently for persistent paper trading only. It analyzes configured
symbols, records decisions, and simulates fills. It does not place real orders.

## Setup

Set `SERVICE_ROOT` before running the bot:

```powershell
$env:SERVICE_ROOT='R:\service'
```

Your personal config lives at:

```text
R:\service\rh_agentic.json
```

The current default polling interval is `60` seconds, controlled by:

```json
"poll_seconds": 60.0
```

## Quote Data

The persistent session reads quote data from the file configured by
`quote_source_path`, currently:

```text
R:\service\rh_quotes.json
```

That file should be maintained by quote-collection code. The user should not
normally type prices into the bot command.

Expected format:

```json
{
  "symbols": {
    "AAPL": {
      "price": 205.0,
      "previous_close": 200.0
    },
    "MSFT": {
      "price": 430.0,
      "previous_close": 425.0
    }
  }
}
```

## Start A Paper Session

From the Python repo root:

```powershell
cd C:\repo\gtvfx\robinhood\py
$env:SERVICE_ROOT='R:\service'
python -m robinhood.agentic.cli run
```

The bot will poll the quote file every `poll_seconds`, analyze each configured
stock symbol, append decisions to `journal_path`, and print a concise status
line for each decision.

To run one polling iteration for a smoke test:

```powershell
python -m robinhood.agentic.cli run --max-iterations 1
```

To temporarily override polling cadence:

```powershell
python -m robinhood.agentic.cli run --poll-seconds 15
```

## One-Shot Analysis

The `analyze` command still accepts `--price` and `--previous-close` for tests,
debugging, and future collector dispatch. Normal users should prefer `run`.

```powershell
python -m robinhood.agentic.cli analyze --symbol AAPL --price 205 --previous-close 200
```

## Stop The Session

Press `Ctrl+C` in the terminal running the bot.

## Output Files

Decision journal:

```text
R:\service\rh_agentic_decisions.jsonl
```

Each line is one JSON decision record with quote, strategy decision, risk result,
and dry-run flag.
