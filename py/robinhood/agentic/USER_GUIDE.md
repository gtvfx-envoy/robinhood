# Agentic Bot User Guide

This bot is currently for persistent paper trading only. In one running process
it collects quotes, analyzes configured lanes, records decisions, and simulates
fills. It does not place real orders.

## Setup

Set `SERVICE_ROOT` before running the bot:

```powershell
$env:SERVICE_ROOT='<PATH TO CONFIG ROOT>'
```

Your personal config lives at:

```text
$env:SERVICE_ROOT\rh_agentic.json
```

The current default polling interval is `60` seconds, controlled by:

```json
"poll_seconds": 60.0
```

## Quote Data

The persistent session now attempts to collect fresh quotes itself. It writes
the latest collected quotes to the file configured by `quote_source_path`,
currently:

```text
$env:SERVICE_ROOT\rh_quotes.json
```

The quote file is also used as a cache/fallback. The user should not normally
type prices into the bot command.

If the quote file does not exist, the bot creates it as an empty JSON object.
If quote collection fails and no cached quote exists for a symbol, the bot prints
`SKIP` for that symbol and waits for the next polling cycle. A partial quote file
is valid; symbols not present in the file are skipped without stopping the
session.

## Lanes

Symbols are grouped into lanes in `config/symbols.cfg`. Each lane can have its
own symbols, strategy, polling interval, and asset class.

Example:

```json
{
  "stocks": {
    "symbols": ["AAPL", "MSFT"],
    "strategy": "simple_momentum",
    "poll_seconds": 60.0,
    "asset_class": "equity"
  },
  "scalps": {
    "symbols": ["NVDA"],
    "strategy": "simple_momentum",
    "poll_seconds": 15.0,
    "asset_class": "equity"
  },
  "crypto": {
    "symbols": ["BTC", "ETH", "SOL"],
    "strategy": "crypto_scalp",
    "poll_seconds": 15.0,
    "asset_class": "crypto"
  }
}
```

The initial crypto lane uses `crypto_scalp`. It is a paper-trading strategy that
waits for short-term price history, then looks for fast EMA above slow EMA, RSI
in a controlled momentum range, and enough estimated edge to clear small
execution costs. Exits use take-profit, stop-loss, and trailing stop checks.

The default crypto polling interval is `15` seconds. That is a practical
starting point for paper scalping with free HTTP quote data: fast enough to catch
small moves, but slow enough to avoid excessive requests and noisy one-tick
signals. Shorter intervals should wait until the quote source, rate limits, and
execution costs are better modeled.

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
$env:SERVICE_ROOT='<PATH TO CONFIG ROOT>'
python -m robinhood.agentic.cli run
```

The bot will poll each lane on that lane's `poll_seconds`, collect quotes,
analyze each configured symbol, append decisions to `journal_path`, and print a
concise status line for each decision.

While waiting between lane polls, the bot prints a countdown progress bar:

```text
[########----------------] next poll: stocks in  39.0s
```

To disable the countdown for logs or scheduled runs:

```powershell
python -m robinhood.agentic.cli run --quiet
```

If the quote collector is not running yet, the session stays alive and prints
skip messages such as:

```text
MSFT: SKIP - quote for MSFT not found in R:\service\rh_quotes.json
```

To run one polling iteration for a smoke test:

```powershell
python -m robinhood.agentic.cli run --max-iterations 1
```

To temporarily override polling cadence:

```powershell
python -m robinhood.agentic.cli run --poll-seconds 15
```

To run without fresh quote collection and only read the existing quote cache:

```powershell
python -m robinhood.agentic.cli run --no-collect
```

## One-Shot Analysis

The `analyze` command still accepts `--price` and `--previous-close` for tests,
debugging, and future collector dispatch. Normal users should prefer `run`.

```powershell
python -m robinhood.agentic.cli analyze --symbol AAPL --price 205 --previous-close 200
```

## Stop The Session

Press `Ctrl+C` in the terminal running the bot.

The bot handles the interrupt cleanly, stops the polling loop, and prints a
summary:

```text
[stop] keyboard interrupt received; stopping paper session
[summary] iterations=4 decisions=32 skipped_quotes=0 collection_errors=0 paper_cash=$9990.00 interrupted=True
```

## Output Files

Decision journal:

```text
$env:SERVICE_ROOT\rh_agentic_decisions.jsonl
```

Each line is one JSON decision record with quote, strategy decision, risk result,
and dry-run flag.
