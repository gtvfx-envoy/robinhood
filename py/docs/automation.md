# Automation

Use `run-daily-daemon` for unattended daily-candle review or live placement.

## Review-Only Daemon

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

## Useful Options

```powershell
--run-at 09:35
--timezone America/New_York
--poll-seconds 60
--max-iterations 1
--max-live-order-dollars 5
```

Use `--max-iterations 1` for smoke tests.
