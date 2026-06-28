# Agentic Technical Notes

This package contains the local agentic trading scaffold. It is intentionally
backtest and paper-trading first. Live order placement should be added only
behind explicit config gates and hard risk caps.

## Architecture

The long-running bot is a single process with four stages:

1. Scheduler selects due lanes.
2. Collector fetches quote snapshots and updates the quote cache.
3. Decision stage dispatches lane symbols to the configured strategy.
4. Executor applies the decision through either the paper account or a configured
   broker-backed review/placement session.

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
  "broker": "paper",
  "dry_run": true,
  "live_trading_enabled": false,
  "auto_place_orders": false,
  "journal_path": "R:/service/rh_agentic_decisions.jsonl",
  "quote_source_path": "R:/service/rh_quotes.json",
  "poll_seconds": 60.0,
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

For future live trading through the Robinhood Agentic MCP broker, `broker` must
be `agentic_mcp`, `dry_run` must be `false`, and both `live_trading_enabled` and
`auto_place_orders` must be set to `true`. Leaving any gate disabled keeps the
MCP broker in review-only mode.

Standalone MCP access requires the optional MCP SDK:

```powershell
python -m pip install "mcp>=1.27,<2"
```

The Streamable HTTP client can send a bearer token from an environment variable
when configured:

```json
{
  "mcp_url": "https://agent.robinhood.com/mcp/trading",
  "mcp_bearer_token_env_var": "RH_MCP_TOKEN"
}
```

For browser OAuth, no client secret is currently expected. Configure where the
standalone process should store the token response, then run `mcp-login`:

```json
{
  "account_number": "551641152",
  "mcp_url": "https://agent.robinhood.com/mcp/trading",
  "mcp_token_store_path": "R:/service/rh_agentic_mcp_tokens.json",
  "mcp_oauth_callback_port": 8765
}
```

If `mcp_token_store_path` is omitted, the CLI stores tokens at
`$env:SERVICE_ROOT\rh_agentic_mcp_tokens.json`. Treat this file like a password
because it can authorize account access.

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

## Strategies

Current strategies:

- `daily_trend_follow`: long-only daily EMA trend following for liquid ETFs and
  stocks. It buys when price and short EMA are above long EMA, avoids large
  one-day spikes, and exits on long EMA break, stop loss, or trailing stop.
- `simple_momentum`: compares current price with previous close.
- `crypto_scalp`: stateful paper scalping strategy for crypto lanes. It keeps
  rolling in-memory price history, enters when fast EMA is above slow EMA with
  RSI inside a controlled momentum band, then exits on take-profit, stop-loss,
  or trailing stop.
- `hold`: always returns `HOLD`.

The tracked default lane is ETF-first: `SPY`, `QQQ`, `IWM`, `TLT`, and `GLD`
using `daily_trend_follow`. Crypto is disabled in tracked config for the first
small-account live path.

`daily_trend_follow` is designed for backtests and future candle-aware
execution. The persistent `run` loop still operates on quote snapshots; do not
use it as the live execution path for daily trend following until the
candle-aware broker session layer is added.

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

`PaperSession` and `BrokerSession` run the persistent loop:

1. Find lanes whose `poll_seconds` interval has elapsed.
2. Collect quotes for each lane and write the JSON quote cache.
3. Fall back to the cache when collection does not return a fresh quote.
4. Skip symbols whose quote is currently unavailable.
5. Run `AgenticBot.analyze()` with the lane's configured strategy.
6. Append a JSONL decision journal entry.
7. Apply approved decisions to `PaperAccount`, or route broker intents through
   MCP review/placement when `broker` is `agentic_mcp`.
8. Sleep until the next lane is due.

Broker-backed sessions append a second JSONL row for each approved trade
decision that reaches broker planning. That row has
`event_type="broker_execution"`, links back to the decision row with
`decision_timestamp`, and records `broker_status`, `broker_reason`,
`order_intent`, placement fields, and a compact MCP review summary when
available.

Each lane controls its own polling cadence in `config/symbols.cfg`.
The session prints lane poll summaries and a countdown progress bar by default.
`show_progress=False` or CLI `--quiet` disables the countdown while preserving
poll and decision lines.
`KeyboardInterrupt` is caught inside `PaperSession.run()` so Ctrl+C returns a
`SessionResult` with `interrupted=True` instead of raising a traceback.

## CLI

One-shot analysis:

```powershell
$env:SERVICE_ROOT='R:\service'
python -m robinhood.agentic.cli analyze --symbol AAPL --price 205 --previous-close 200
```

Backtest the ETF universe with the $100 account constraints as one shared-cash
portfolio:

```powershell
$env:SERVICE_ROOT='R:\service'
python -m robinhood.agentic.cli backtest --portfolio --range 1y --starting-cash 100 --target-dollars 10 --min-order-dollars 1 --max-trade-dollars 15 --min-cash-reserve 50 --max-open-positions 2 --max-new-buys-per-day 1 --max-daily-trades 2 --max-total-exposure-dollars 50
```

Check Agentic MCP broker connectivity in review-only mode:

```powershell
$env:SERVICE_ROOT='R:\service'
python -m robinhood.agentic.cli mcp-login
python -m robinhood.agentic.cli mcp-check --symbol SPY
```

`mcp-login` opens the Robinhood authorization page in a browser and listens on
`http://127.0.0.1:<mcp_oauth_callback_port>/callback` for the OAuth redirect.
`mcp-check` reviews a $1 SPY buy through the Agentic MCP broker but does not
place an order.

Review-only connectivity check after login:

```powershell
python -m robinhood.agentic.cli mcp-check --symbol SPY
```

Review a specific dollar-sized buy without placing it:

```powershell
python -m robinhood.agentic.cli mcp-review --symbol SPY --dollars 1
```

`mcp-review` is always review-only. It prints account cash, position count,
review approval, estimated quantity/cost when returned by MCP, and any review
alerts.

Check whether the current config is ready for live placement without placing an
order:

```powershell
python -m robinhood.agentic.cli live-check --symbol SPY --dollars 1
```

`live-check` is also review-only. It fails unless `broker=agentic_mcp`,
`dry_run=false`, `live_trading_enabled=true`, `auto_place_orders=true`, risk
limits are coherent, the account has usable cash after reserve, the symbol is
allowed, and MCP approves the readiness review.

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
