# Getting Started

Run commands from the Python repo root:

```powershell
cd <REPO_ROOT>\py
```

Set `SERVICE_ROOT` to the private config/state directory:

```powershell
$env:SERVICE_ROOT = "<SERVICE_ROOT>"
```

The personal config is loaded from:

```text
$env:SERVICE_ROOT\rh_agentic.json
```

That file should contain account identifiers, local state paths, risk limits,
and live-trading gates. Keep it outside the repository.

## Minimal Conservative Config

```json
{
  "account_number": "YOUR_ACCOUNT_NUMBER",
  "broker": "agentic_mcp",
  "dry_run": false,
  "live_trading_enabled": false,
  "auto_place_orders": false,
  "live_order_confirm": "",
  "journal_path": "<SERVICE_ROOT>/rh_agentic_decisions.jsonl",
  "quote_source_path": "<SERVICE_ROOT>/rh_quotes.json",
  "paper_starting_cash": 100.0,
  "risk": {
    "min_order_dollars": 1.0,
    "max_trade_dollars": 5.0,
    "max_daily_trades": 1,
    "max_new_buys_per_day": 1,
    "max_open_positions": 2,
    "min_cash_reserve": 50.0,
    "max_total_exposure_dollars": 10.0,
    "allow_shorts": false,
    "allow_options": false
  }
}
```

With `live_trading_enabled=false` or `auto_place_orders=false`, MCP broker
commands stay in review-only behavior.

## Optional MCP SDK

Standalone MCP access requires the MCP SDK:

```powershell
python -m pip install -r robinhood\agentic\requirements.txt
```

Authenticate once when using browser OAuth:

```powershell
python -m robinhood.agentic.cli mcp-login
```
