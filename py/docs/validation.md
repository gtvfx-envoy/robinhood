# Strategy and Broker Validation

## Research protocol

Do not treat a backtest as a deployment recommendation. Every report must
record the candle source, retrieval date, universe, strategy revision,
parameters, execution assumptions, and evaluation period. Run a fixed
calibration period followed by an untouched out-of-sample period. Repeat with
adverse slippage, spread, gaps, missing data, and parameter perturbations.

Use the portfolio backtest rather than combining isolated symbol results; it
applies the shared-cash, position, exposure, and daily-trade constraints.
Generated account data and research outputs belong outside the repository or in
an explicitly reviewed, sanitized artifact directory.

## MCP contract check

Before a paper or live-pilot session, use only these read-only/review-only
commands:

```powershell
python -m robinhood.agentic.cli mcp-tools --filter equity
python -m robinhood.agentic.cli mcp-check --symbol SPY
python -m robinhood.agentic.cli mcp-review --symbol SPY --dollars 1
python -m robinhood.agentic.cli mcp-orders --symbol SPY --limit 5
```

Record sanitized responses for portfolio, positions, tradability, review, and
order readback whenever the MCP schema changes. Unknown placement payloads must
remain unconfirmed and block further automation until reconciliation.

No command in this protocol places an order. `mcp-place-once` remains a
separate, explicitly authorized live-pilot operation.
