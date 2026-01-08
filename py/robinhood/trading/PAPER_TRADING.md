# Paper Trading Mode

## Overview

Paper trading allows you to test your trading strategy with simulated trades **without risking real money**. This is essential for validating your strategy before committing actual capital.

## What is Paper Trading?

Paper trading simulates all trading operations:
- ✅ **Simulated orders**: No real market orders are placed
- ✅ **Virtual balance**: Tracks simulated cash and equity
- ✅ **Realistic behavior**: Uses actual market prices from your exchange
- ✅ **Full strategy testing**: All indicators, ML predictions, and signals work normally
- ✅ **Risk-free**: Zero financial risk while testing

## Quick Start

### Enable Paper Trading in Config

```python
from trading_bot import TradingConfig, TradingBot

config = TradingConfig(
    trading_pairs=["BTC-USD", "ETH-USD"],
    position_size_percent=10.0,
    paper_trading=True,  # Enable paper trading
    paper_trading_balance=10000.0  # Starting virtual balance
)

bot = TradingBot(adapter, config)
bot.run(iterations=10)  # Test with 10 cycles
```

### Override at Runtime

```python
# Start with paper trading disabled
config = TradingConfig(paper_trading=False)
bot = TradingBot(adapter, config)

# Override to paper trading when calling run()
bot.run(iterations=20, paper_trading=True)
```

## Configuration Parameters

### `paper_trading` (bool)
- **Default**: `False`
- **Description**: Enable/disable paper trading mode
- **Usage**: Set to `True` to simulate trades

### `paper_trading_balance` (float)
- **Default**: `10000.0`
- **Description**: Starting virtual balance in USD
- **Usage**: Set to whatever amount you plan to trade with live

## How It Works

### Position Opening (Paper Mode)
1. Bot generates trading signal normally
2. Instead of placing real order via exchange API:
   - Creates simulated order with current market price
   - Deducts position value from `paper_balance`
   - Adds position value to `paper_equity`
3. Position is tracked like normal position

### Position Closing (Paper Mode)
1. Bot detects exit signal (stop-loss, take-profit, etc.)
2. Instead of placing real closing order:
   - Calculates current position value at market price
   - Adds value back to `paper_balance`
   - Subtracts from `paper_equity`
3. P&L is calculated and recorded

### Balance Tracking
- **`paper_balance`**: Virtual cash available for new positions
- **`paper_equity`**: Virtual value of open positions
- **Total Portfolio**: `paper_balance + paper_equity`

## Monitoring Paper Trading

### Status Display

The bot displays paper trading status clearly:

```
======================================================================
[PAPER TRADING MODE] Trading Bot Status - 2026-01-07 15:30:00
======================================================================

Paper Trading Balance: $8,500.00
Paper Equity Value: $1,500.00
Total Portfolio Value: $10,000.00
Daily P&L: $+50.00
```

### Order Execution

Paper orders are marked with `[PAPER]`:

```
📊 [PAPER] Opening BUY position: BTC-USD
   Price: $50,000.00
   Quantity: 0.01700000
   Confidence: 85.23%
```

## Best Practices

### 1. Test Thoroughly
```python
# Run multiple cycles to test different market conditions
bot.run(iterations=50, paper_trading=True)
```

### 2. Use Realistic Balance
```python
# If you plan to trade with $5000, use that in paper trading
config = TradingConfig(
    paper_trading=True,
    paper_trading_balance=5000.0  # Match your actual capital
)
```

### 3. Monitor Performance
```python
# Track your paper trading results
initial = config.paper_trading_balance
final = bot.paper_balance + bot.paper_equity
pnl = final - initial
pnl_pct = (pnl / initial) * 100

print(f"Paper Trading P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
```

### 4. Gradual Transition to Live

```python
# Step 1: Test extensively in paper mode
config.paper_trading = True
bot.run(iterations=100)

# Step 2: Once confident, switch to live with TINY positions
config.paper_trading = False
config.position_size_percent = 1.0  # Start with 1% only!
bot.run(iterations=10)  # Test live with small amount

# Step 3: Gradually increase if successful
config.position_size_percent = 5.0
```

## Limitations

### What Paper Trading Cannot Do

1. **Slippage**: Paper trading uses exact market prices
   - Real trades may execute at slightly different prices
   - More noticeable in low-liquidity markets

2. **Order Rejection**: Paper trades always "fill"
   - Real exchanges may reject orders for various reasons
   - Account limits, exchange maintenance, etc.

3. **Latency**: Paper trades execute instantly
   - Real trades have network latency
   - Prices may move between signal and execution

4. **Emotions**: No psychological pressure
   - Paper losses don't feel real
   - Live trading requires emotional discipline

### Working Around Limitations

```python
# Add commission simulation to paper trading
# (Currently not implemented, but can be added)

# Calculate realistic expectations
paper_profit = 1000  # Your paper trading profit
estimated_live_profit = paper_profit * 0.95  # Account for 5% friction
```

## Example Workflow

### Complete Paper Trading Test

```python
import os
from robinhood.trading import RobinhoodClient, RobinhoodExchangeAdapter
from trading_bot import TradingBot, TradingConfig

# Setup
client = RobinhoodClient(
    os.getenv("ROBINHOOD_API_KEY"),
    os.getenv("ROBINHOOD_PRIVATE_KEY")
)
adapter = RobinhoodExchangeAdapter(client)

# Configure with paper trading
config = TradingConfig(
    trading_pairs=["BTC-USD", "ETH-USD"],
    position_size_percent=10.0,
    max_positions=2,
    stop_loss_percent=3.0,
    take_profit_percent=5.0,
    paper_trading=True,
    paper_trading_balance=10000.0
)

# Run paper trading
bot = TradingBot(adapter, config)

print("🧪 Starting paper trading test...")
bot.run(iterations=50)

# Evaluate results
initial = config.paper_trading_balance
final = bot.paper_balance + bot.paper_equity
pnl = final - initial
pnl_pct = (pnl / initial) * 100

print(f"\n📊 Paper Trading Results:")
print(f"   Initial: ${initial:,.2f}")
print(f"   Final:   ${final:,.2f}")
print(f"   P&L:     ${pnl:+,.2f} ({pnl_pct:+.2f}%)")

# Decide next step
if pnl_pct > 5.0:
    print("\n✅ Good results! Consider live trading with small amounts")
elif pnl_pct > 0:
    print("\n⚠️  Slightly profitable. Test more or adjust strategy")
else:
    print("\n❌ Strategy needs improvement. Keep paper trading")
```

## Switching to Live Trading

### Safety Checklist

Before going live, verify:

- [ ] Paper trading shows consistent profitability over 50+ cycles
- [ ] You understand why your strategy works
- [ ] You've tested in different market conditions (trending, sideways, volatile)
- [ ] Your risk management is solid (stop-loss, position sizing)
- [ ] You have emotional discipline for real money
- [ ] You start with **very small** position sizes (1-2%)
- [ ] You can afford to lose your trading capital

### Safe Transition

```python
# Phase 1: Paper trading (extensive testing)
config = TradingConfig(
    position_size_percent=10.0,
    paper_trading=True,
    paper_trading_balance=10000.0
)
bot.run(iterations=100)

# Phase 2: Micro live trading
config.paper_trading = False
config.position_size_percent = 1.0  # 1% only!
bot.run(iterations=10)  # Very limited live test

# Phase 3: Small live trading
if all_tests_successful():
    config.position_size_percent = 3.0  # Gradually increase
    bot.run(iterations=50)

# Phase 4: Full live (only after proven success)
if consistent_profits():
    config.position_size_percent = 5.0
    bot.run()  # Unlimited
```

## Troubleshooting

### Paper Balance Goes Negative?
This shouldn't happen, but if it does:
```python
# Check your position_size_percent
# Make sure it's not too high
config.position_size_percent = 5.0  # Lower value
```

### Unrealistic Profits in Paper Mode?
```python
# Your strategy might be overfitting
# Test with longer periods and different pairs
config.trading_pairs = ["BTC-USD", "ETH-USD", "DOGE-USD"]
bot.run(iterations=100)  # More data points
```

### Can't Switch from Paper to Live?
```python
# Create new bot instance with updated config
config.paper_trading = False
bot = TradingBot(adapter, config)  # Fresh start
bot.run()
```

## Summary

✅ **Always test new strategies in paper mode first**  
✅ **Use realistic balance and position sizes**  
✅ **Run extensive testing (50+ cycles minimum)**  
✅ **Transition to live gradually with tiny positions**  
✅ **Never risk money you can't afford to lose**

Paper trading is your safety net. Use it!
