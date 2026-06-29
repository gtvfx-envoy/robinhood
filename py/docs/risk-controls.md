# Risk Controls

Risk controls are enforced before broker review or placement.

## Order Caps

`min_order_dollars`
: Rejects orders below the broker/account minimum selected for this bot.

`max_trade_dollars`
: Caps one planned order.

`max_live_order_dollars`
: Additional daemon/broker adapter cap used by live MCP placement paths.

## Portfolio Caps

`max_open_positions`
: Caps the number of symbols held by the bot.

`max_total_exposure_dollars`
: Caps deployed capital across bot-managed positions.

For example, if the bot already holds about `$1` of `SPY` and wants to buy `$5`
of `QQQ`, the portfolio exposure check needs room for roughly `$6` total.

`min_cash_reserve`
: Cash that must remain untouched.

## Daily Trade Caps

`max_new_buys_per_day`
: Caps new buy entries per trading day.

`max_daily_trades`
: Caps total daily trade actions.

## Live Gates

Live placement also requires all explicit gates:

```json
{
  "broker": "agentic_mcp",
  "dry_run": false,
  "live_trading_enabled": true,
  "auto_place_orders": true,
  "live_order_confirm": "I_UNDERSTAND_THIS_CAN_PLACE_REAL_ORDERS"
}
```

Leaving any live gate disabled keeps the broker in review-only mode.
