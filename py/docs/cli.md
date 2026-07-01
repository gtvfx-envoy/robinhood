# CLI

The main entrypoint is:

```powershell
python -m robinhood.agentic.cli
```

## Review Broker Connectivity

```powershell
python -m robinhood.agentic.cli mcp-check --symbol SPY
python -m robinhood.agentic.cli mcp-review --symbol SPY --dollars 1
```

These commands review orders but do not place live orders.

## Check Live Readiness

```powershell
python -m robinhood.agentic.cli live-check --symbol SPY --dollars 1
```

`live-check` fails until every live gate is intentional:

- `broker=agentic_mcp`
- `dry_run=false`
- `live_trading_enabled=true`
- `auto_place_orders=true`
- `live_order_confirm=I_UNDERSTAND_THIS_CAN_PLACE_REAL_ORDERS`
- coherent risk limits
- usable account cash after reserve
- allowed symbol
- approved MCP review

## Daily Review

```powershell
python -m robinhood.agentic.cli run-daily --review-only --candle-file <SERVICE_ROOT>\rh_daily_candles.json --range 1y
```

Use what-if overrides to test risk changes without changing personal config:

```powershell
python -m robinhood.agentic.cli run-daily --review-only --what-if-max-open-positions 2 --what-if-max-total-exposure-dollars 50 --candle-file <SERVICE_ROOT>\rh_daily_candles.json --range 1y
```

## Read Orders

```powershell
python -m robinhood.agentic.cli mcp-orders --symbol SPY --limit 5
python -m robinhood.agentic.cli mcp-orders --order-id <broker-order-id>
python -m robinhood.agentic.cli mcp-reconcile-orders --symbol SPY --dry-run
```

`mcp-orders` and `mcp-reconcile-orders` are read-only against Robinhood.
