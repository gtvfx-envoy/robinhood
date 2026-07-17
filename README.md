# Robinhood Agentic Trading Bot

This repository contains a Python-based agentic trading bot for Robinhood. The
current focus is the `robinhood.agentic` package: a conservative, auditable
daily-candle trading daemon that can review and place small live equity orders
through Robinhood Agentic MCP.

The bot is designed around explicit live-trading gates, hard risk limits,
persistent daemon state, broker readback reconciliation, and JSONL decision
journals. It is intended for controlled automation, not unattended high-risk
trading.

## Documentation

Published documentation:

- [Documentation Site](https://gtvfx-contrib.github.io/robinhood/)
- [Getting Started](https://gtvfx-contrib.github.io/robinhood/getting-started/)
- [CLI Reference](https://gtvfx-contrib.github.io/robinhood/cli/)
- [Risk Controls](https://gtvfx-contrib.github.io/robinhood/risk-controls/)
- [Automation](https://gtvfx-contrib.github.io/robinhood/automation/)
- [Legal and Trading Disclaimer](DISCLAIMER.md)
- [API Reference](https://gtvfx-contrib.github.io/robinhood/api/)

Local source docs live under [py/docs](py/docs). The MkDocs site is built from
[py/mkdocs.yml](py/mkdocs.yml) and published by
[deploy-docs.yml](.github/workflows/deploy-docs.yml).

## What Is In This Repo

- `py/robinhood/agentic`: the active agentic trading bot package.
- `py/docs`: MkDocs documentation and generated API reference pages.
- `py/tests`: focused unit tests for config, strategy, daemon state, broker
  behavior, MCP parsing, and CLI workflows.
- `.github/workflows`: CI plus GitHub Pages documentation deployment.

Older Robinhood crypto API experiments may still exist in the repository, but
the maintained runtime path is the `robinhood.agentic` package.

## Core Runtime

The persistent daemon command is:

```powershell
$env:SERVICE_ROOT='<SERVICE_ROOT>'
en agentic run-daemon --candle-file <SERVICE_ROOT>\rh_daily_candles.json --range 1y --exit-when-done
```

The daemon:

- uses regular-market clock state before trading
- refreshes daily candles during pre-open warmup
- evaluates configured daily trend lanes
- places live orders only when explicit config gates are enabled
- blocks additional orders while a submitted order is pending confirmation
- reconciles broker readback before continuing
- exits cleanly with `--exit-when-done` when no more trades can be made today

## Private Runtime Files

Keep account-specific configuration and trading state outside the repo. Set
`SERVICE_ROOT` to that private runtime directory:

```text
<SERVICE_ROOT>
```

Important files:

- `<SERVICE_ROOT>\rh_agentic.json`: personal config, live gates, account number,
  and risk limits.
- `<SERVICE_ROOT>\rh_agentic_state.json`: persistent daemon state.
- `<SERVICE_ROOT>\rh_agentic_decisions.jsonl`: decision and execution journal.
- `<SERVICE_ROOT>\rh_daily_candles.json`: daily candle cache.

Repo-local `logs/` directories are ignored intentionally. Trading logs can
contain order identifiers, symbols, timestamps, fills, and account-sensitive
runtime data.

## Development

Run commands from the Python project root:

```powershell
cd py
python -m pip install -r requirements-dev.txt
```

Common checks:

```powershell
python -m ruff check robinhood\agentic tests\test_agentic.py
python -m ruff format --check robinhood\agentic tests\test_agentic.py
python -m unittest discover -s tests -p test_agentic.py
python -m mkdocs build --strict
```

Serve docs locally:

```powershell
python -m mkdocs serve
```

## Automation

For scheduled runs, prefer `run-daemon --exit-when-done`. This lets Task
Scheduler or a service wrapper start the bot, let it reconcile and trade within
configured limits, and exit once the trading day is complete or capacity is
exhausted.

See the [Automation documentation](https://gtvfx-contrib.github.io/robinhood/automation/)
for daemon behavior, state reconciliation, market calendar support, and useful
operator commands.

## Safety Notice

This software can place real orders when live gates are enabled. Review the risk
configuration and start with small caps. This is not financial advice, and past
strategy behavior does not guarantee future results. Read the
[Legal and Trading Disclaimer](DISCLAIMER.md) before using live trading features.
