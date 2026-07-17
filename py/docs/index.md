# Robinhood Agentic Bot

This documentation covers the local agentic trading bot package under
`robinhood.agentic`.

The bot is built around a conservative progression:

1. Backtest strategy behavior.
2. Run review-only broker checks.
3. Place a small controlled live order.
4. Run the daily-candle daemon with hard live gates and risk caps.

The code intentionally keeps live order placement behind explicit config gates,
small dollar caps, journaled audit events, and broker-side review.

## Documentation Map

- [Getting Started](getting-started.md): environment and config basics.
- [CLI](cli.md): common command-line workflows.
- [Risk Controls](risk-controls.md): how the portfolio and order caps work.
- [Automation](automation.md): daily daemon operation.
- [Deployment Readiness](readiness.md): stage gates and incident procedure.
- [Validation Protocol](validation.md): research and read-only MCP checks.
- [API Reference](api/index.md): generated Python reference via `mkdocstrings`.

## Build The Docs

Install the docs dependencies from the Python repo root:

```powershell
python -m pip install -r requirements-docs.txt
```

Build the static site:

```powershell
python -m mkdocs build
```

Serve it locally while editing:

```powershell
python -m mkdocs serve
```
