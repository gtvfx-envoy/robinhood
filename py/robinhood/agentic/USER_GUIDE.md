# Agentic Bot User Guide

This bot is currently for backtesting and persistent paper trading only. It does
not place real orders yet.

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
    "symbols": ["SPY", "QQQ", "IWM", "TLT", "GLD"],
    "strategy": "daily_trend_follow",
    "poll_seconds": 86400.0,
    "asset_class": "equity"
  }
}
```

The first recommended lane uses `daily_trend_follow`. It is a long-only daily
trend strategy for liquid ETFs and stocks. It buys only when price and short EMA
are above the long EMA, filters large one-day spikes, and exits on long EMA
breaks, stop loss, or trailing stop.

For a $100 cash account, use conservative risk settings in
`$env:SERVICE_ROOT\rh_agentic.json`:

```json
{
  "broker": "paper",
  "live_trading_enabled": false,
  "auto_place_orders": false,
  "live_order_confirm": "",
  "paper_starting_cash": 100.0,
  "risk": {
    "min_order_dollars": 1.0,
    "max_trade_dollars": 15.0,
    "max_daily_trades": 2,
    "max_new_buys_per_day": 1,
    "max_open_positions": 2,
    "min_cash_reserve": 50.0,
    "max_total_exposure_dollars": 50.0,
    "allow_shorts": false,
    "allow_options": false
  }
}
```

For future unattended live trading through the Robinhood Agentic MCP account,
`broker` must be `agentic_mcp`, `dry_run` must be `false`, and both
`live_trading_enabled` and `auto_place_orders` must be `true`.
`live_order_confirm` must also match the exact phrase
`I_UNDERSTAND_THIS_CAN_PLACE_REAL_ORDERS`. Keep any gate disabled for
review-only mode.
Standalone MCP access also requires the optional MCP SDK:

```powershell
python -m pip install "mcp>=1.27,<2"
```

If your standalone process receives an MCP bearer token through an environment
variable, set:

```json
{
  "mcp_url": "https://agent.robinhood.com/mcp/trading",
  "mcp_bearer_token_env_var": "RH_MCP_TOKEN"
}
```

For the browser OAuth path, you do not need to provide a client secret. Add the
account number and, optionally, a token-store path:

```json
{
  "account_number": "551641152",
  "mcp_url": "https://agent.robinhood.com/mcp/trading",
  "mcp_token_store_path": "R:/service/rh_agentic_mcp_tokens.json",
  "mcp_oauth_callback_port": 8765
}
```

If `mcp_token_store_path` is omitted, the bot uses:

```text
$env:SERVICE_ROOT\rh_agentic_mcp_tokens.json
```

Treat that token file like a password because it can authorize account access.
Run this once to start the browser authorization flow:

```powershell
python -m robinhood.agentic.cli mcp-login
```

The CLI opens Robinhood in the browser and listens locally at
`http://127.0.0.1:<mcp_oauth_callback_port>/callback` for the OAuth redirect.

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

The persistent `run` loop still uses quote snapshots. When `broker` is
`agentic_mcp`, approved trade decisions are converted into broker intents and
sent through MCP review-only mode unless all live-placement gates are enabled.
The daily trend strategy requires historical daily candles, so use `backtest`
for this strategy until the candle-aware broker session is added.

## Backtest The ETF Strategy

From the Python repo root:

```powershell
cd C:\repo\gtvfx\robinhood\py
$env:SERVICE_ROOT='<PATH TO CONFIG ROOT>'
python -m robinhood.agentic.cli backtest --portfolio --range 1y --starting-cash 100 --target-dollars 10 --min-order-dollars 1 --max-trade-dollars 15 --min-cash-reserve 50 --max-open-positions 2 --max-new-buys-per-day 1 --max-daily-trades 2 --max-total-exposure-dollars 50
```

To test one symbol:

```powershell
python -m robinhood.agentic.cli backtest --symbol SPY --range 6mo --starting-cash 100 --target-dollars 10 --min-order-dollars 1 --max-trade-dollars 15 --min-cash-reserve 50
```

To check MCP broker connectivity without placing an order:

```powershell
$env:SERVICE_ROOT='<PATH TO CONFIG ROOT>'
python -m robinhood.agentic.cli mcp-login
python -m robinhood.agentic.cli mcp-check --symbol SPY
```

`mcp-check` reviews a $1 buy for the selected symbol and keeps the broker in
review-only mode.

To review a specific dollar-sized buy without placing it:

```powershell
python -m robinhood.agentic.cli mcp-review --symbol SPY --dollars 1
```

`mcp-review` is always review-only and prints account cash, position count,
review approval, estimated quantity/cost when returned, and review alerts.

To check live-placement readiness without placing an order:

```powershell
python -m robinhood.agentic.cli live-check --symbol SPY --dollars 1
```

`live-check` returns `FAIL` until every live gate is intentional:
`broker=agentic_mcp`, `dry_run=false`, `live_trading_enabled=true`,
`auto_place_orders=true`, the exact `live_order_confirm` phrase is present,
coherent risk limits, usable account cash after reserve, an allowed symbol, and
an approved MCP review.

As a final guard, the live MCP broker adapter also rejects placement when order
notional exceeds `risk.max_trade_dollars`.

The live broker adapter also has a one-order-per-process fuse. After one live
order is submitted, later placement attempts in that process are rejected before
the MCP placement tool is called again.

For a controlled first live order, use:

```powershell
python -m robinhood.agentic.cli mcp-place-once --symbol SPY --dollars 1
```

`mcp-place-once` runs the same readiness checks, submits at most one order, and
records a `broker_execution` event in the journal.

Read back order state without placing anything:

```powershell
python -m robinhood.agentic.cli mcp-orders --symbol SPY --limit 5
python -m robinhood.agentic.cli mcp-orders --order-id <broker-order-id>
```

Append read-only status snapshots for broker execution journal rows:

```powershell
python -m robinhood.agentic.cli mcp-reconcile-orders --symbol SPY --dry-run
python -m robinhood.agentic.cli mcp-reconcile-orders --symbol SPY
```

For MCP diagnostics, list available tools:

```powershell
python -m robinhood.agentic.cli mcp-tools --filter order
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

When `broker` is `agentic_mcp`, approved trade decisions also get a linked
`broker_execution` row. It records the planned order intent, broker status,
broker reason, placement fields, and a compact MCP review summary when
available.
