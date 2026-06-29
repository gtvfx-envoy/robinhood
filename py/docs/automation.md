# Automation

Use `run-daemon` for persistent market-aware operation. Keep
`run-daily-daemon` for smoke tests and controlled daily-pass checks.

## Persistent Daemon

```powershell
python -m robinhood.agentic.cli run-daemon --candle-file R:\service\rh_daily_candles.json --range 1y --max-live-order-dollars 5
```

The persistent daemon:

- uses a market clock for regular-hours trading
- refreshes daily candles during pre-open warmup
- sleeps when the market is closed instead of pinging constantly
- stores restart-safe operational state in `$SERVICE_ROOT\rh_agentic_state.json`
- enforces daily live order attempt and notional limits from state
- blocks new live orders while an order is pending or unconfirmed

Check the clock and state without trading:

```powershell
python -m robinhood.agentic.cli market-clock
python -m robinhood.agentic.cli run-daemon --status-only --candle-file R:\service\rh_daily_candles.json
```

## Daily Smoke Daemon

Review-only daily pass:

```powershell
python -m robinhood.agentic.cli run-daily-daemon --review-only --candle-file R:\service\rh_daily_candles.json --range 1y
```

By default, the daemon checks once per minute and runs one daily pass at
`09:35 America/New_York`.

## Live-Capped Daemon

After live config gates are intentionally enabled:

```powershell
python -m robinhood.agentic.cli run-daily-daemon --candle-file R:\service\rh_daily_candles.json --range 1y --max-live-order-dollars 5
```

The daemon:

- applies a per-order live cap
- reuses the daily-candle broker session
- reconciles placed MCP orders before journaling
- appends a `daily_daemon_pass` journal marker
- skips a trading day that already has a completion marker

## Rerun Today

If a daily pass already wrote a completion marker but config was later fixed,
rerun the current trading day explicitly:

```powershell
python -m robinhood.agentic.cli run-daily-daemon --rerun-today --max-iterations 1 --candle-file R:\service\rh_daily_candles.json --range 1y --max-live-order-dollars 5
```

`--rerun-today` ignores only today's existing `daily_daemon_pass` marker in
memory. The daemon still writes a new completion marker after the rerun.

## Useful Options

```powershell
--run-at 09:35
--timezone America/New_York
--poll-seconds 60
--max-iterations 1
--rerun-today
--max-live-order-dollars 5
```

Use `--max-iterations 1` for smoke tests.
