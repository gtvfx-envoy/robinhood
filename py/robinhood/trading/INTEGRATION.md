# Robinhood + Trading Bot Integration

This adapter allows you to use the generic `trading_bot` framework with your Robinhood account.

## Features

✅ **Full Exchange Interface**: Implements all required methods from `trading_bot.ExchangeClient`  
✅ **Account Management**: Check balances, buying power, and holdings  
✅ **Order Execution**: Place market and limit orders  
✅ **Order Management**: Check status, cancel orders, view open orders  
✅ **Real-time Prices**: Get current market prices for crypto pairs  

## Installation

Ensure both packages are available:

```bash
# From the repo root
pip install -e trading_bot/py
pip install -e robinhood/py
```

## Quick Start

### ⚠️ Start with Paper Trading!

**Always test your strategy in paper trading mode first** to avoid risking real money:

```python
from robinhood.trading import RobinhoodClient, RobinhoodExchangeAdapter
from trading_bot import TradingBot, TradingConfig
import os

# Setup client
api_key = os.getenv("ROBINHOOD_API_KEY")
private_key = os.getenv("ROBINHOOD_PRIVATE_KEY")
client = RobinhoodClient(api_key, private_key)
adapter = RobinhoodExchangeAdapter(client)

# Configure with paper trading enabled
config = TradingConfig(
    trading_pairs=["BTC-USD", "ETH-USD"],
    position_size_percent=5.0,
    stop_loss_percent=3.0,
    take_profit_percent=5.0,
    paper_trading=True,  # 🧪 Test without real money!
    paper_trading_balance=10000.0
)

# Test your strategy safely
bot = TradingBot(adapter, config)
bot.run(iterations=50)  # Run limited cycles

# Only switch to live after extensive testing
# config.paper_trading = False
# bot.run()
```

See [PAPER_TRADING.md](PAPER_TRADING.md) for complete paper trading guide.

### Option 1: Direct Initialization (Simplest)

```python
from robinhood.trading import RobinhoodClient, RobinhoodExchangeAdapter
from trading_bot import TradingBot, TradingConfig
import os

# Get your API credentials
api_key = os.getenv("ROBINHOOD_API_KEY")
private_key = os.getenv("ROBINHOOD_PRIVATE_KEY")

# Create client directly - no password needed!
client = RobinhoodClient(api_key, private_key)

# 2. Create adapter
adapter = RobinhoodExchangeAdapter(client)

# 3. Configure trading bot
config = TradingConfig(
    trading_pairs=["BTC-USD", "ETH-USD"],
    position_size_percent=5.0,
    stop_loss_percent=3.0,
    take_profit_percent=5.0
)

# 4. Initialize bot (adapter first, then config)
bot = TradingBot(adapter, config)

# 5. Start trading
bot.run()
```

**Setting environment variables:**

```bash
# Windows PowerShell
$env:ROBINHOOD_API_KEY="your-api-key"
$env:ROBINHOOD_PRIVATE_KEY="your-private-key-base64"

# Windows CMD
set ROBINHOOD_API_KEY=your-api-key
set ROBINHOOD_PRIVATE_KEY=your-private-key-base64

# Linux/Mac
export ROBINHOOD_API_KEY="your-api-key"
export ROBINHOOD_PRIVATE_KEY="your-private-key-base64"
```

### Option 2: Encrypted Storage (Optional - More Secure)

If you prefer not to store credentials in environment variables, use KeyManager for encrypted storage:

```bash
# One-time setup
python -m robinhood.trading.setup_keys
```

Then in your code:

```python
from robinhood.trading import RobinhoodClient, KeyManager, RobinhoodExchangeAdapter

# Load from encrypted storage
manager = KeyManager()
password = input("Enter password: ")
client = RobinhoodClient.from_key_manager(manager, password=password)

# Create adapter
adapter = RobinhoodExchangeAdapter(client)

# Use with bot (adapter first!)
config = TradingConfig(trading_pairs=["BTC-USD"])
bot = TradingBot(adapter, config)
```

## Architecture

```
┌─────────────────────────────────────┐
│         Trading Bot                 │
│  (Strategy, Indicators, ML)         │
└─────────────┬───────────────────────┘
              │
              │ ExchangeClient Interface
              │
┌─────────────▼───────────────────────┐
│  RobinhoodExchangeAdapter           │
│  (Implements ExchangeClient)        │
└─────────────┬───────────────────────┘
              │
              │ Robinhood API
              │
┌─────────────▼───────────────────────┐
│     RobinhoodClient                 │
│  (Low-level API wrapper)            │
└─────────────────────────────────────┘
```

## API Coverage

### ✅ Fully Implemented

| Method | Description | Status |
|--------|-------------|--------|
| `get_account_balance()` | Get all asset balances | ✅ |
| `get_buying_power()` | Get available USD | ✅ |
| `get_current_price()` | Get market price | ✅ |
| `place_market_order()` | Execute market order | ✅ |
| `place_limit_order()` | Place limit order | ✅ |
| `cancel_order()` | Cancel pending order | ✅ |
| `get_order_status()` | Check order details | ✅ |
| `get_open_orders()` | List pending orders | ✅ |
| `get_holdings()` | Get crypto positions | ✅ |

### ⚠️ Limitations

| Method | Status | Notes |
|--------|--------|-------|
| `get_historical_candles()` | ⚠️ Not implemented | Robinhood doesn't provide historical OHLCV data via their API. You'll need to integrate with a third-party data provider (e.g., CoinGecko, CryptoCompare) |
| `place_stop_loss_order()` | ❌ Not supported | Robinhood crypto API doesn't support stop-loss orders |

## Examples

See the `examples/` directory:

- **`quickstart_integration.py`** - Minimal integration example
- **`use_with_trading_bot.py`** - Full trading bot implementation
- **`basic_usage.py`** - Direct Robinhood client usage

## Usage Example

### Check Account Balance

```python
adapter = RobinhoodExchangeAdapter(client)

# Get all balances
balances = adapter.get_account_balance()
print(balances)  # {'USD': 10000.0, 'BTC': 0.5, 'ETH': 2.0}

# Get buying power
power = adapter.get_buying_power()
print(f"Available: ${power:,.2f}")
```

### Place Orders

```python
# Market order
order = adapter.place_market_order(
    symbol="BTC-USD",
    side="buy",
    quantity=0.001
)
print(f"Order ID: {order['id']}, Status: {order['status']}")

# Limit order
order = adapter.place_limit_order(
    symbol="ETH-USD",
    side="sell",
    quantity=0.1,
    price=3500.0
)

# Check order status
status = adapter.get_order_status(order['id'])
print(f"Filled: {status['filled_quantity']}")

# Cancel order
adapter.cancel_order(order['id'])
```

### Monitor Positions

```python
# Get holdings
holdings = adapter.get_holdings()
for asset, qty in holdings.items():
    price = adapter.get_current_price(f"{asset}-USD")
    value = qty * price
    print(f"{asset}: {qty:.8f} (${value:,.2f})")

# Get open orders
orders = adapter.get_open_orders()
for order in orders:
    print(f"{order['side']} {order['symbol']} {order['quantity']}")
```

## Historical Data Workaround

Since Robinhood doesn't provide historical candles, you can integrate a data provider:

```python
import ccxt

class RobinhoodWithHistoricalData(RobinhoodExchangeAdapter):
    """Extended adapter with historical data from another exchange."""
    
    def __init__(self, client: RobinhoodClient):
        super().__init__(client)
        self.data_provider = ccxt.coinbase()
    
    def get_historical_candles(self, symbol, start, end, granularity):
        # Fetch from Coinbase for chart data
        # But still trade on Robinhood
        timeframe = self._convert_granularity(granularity)
        ohlcv = self.data_provider.fetch_ohlcv(
            symbol, timeframe, 
            since=int(start.timestamp() * 1000),
            limit=1000
        )
        
        df = pd.DataFrame(
            ohlcv, 
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
```

## Safety Features

The adapter includes:
- Account info caching (5 second TTL) to avoid rate limits
- Comprehensive error handling
- Type hints for all methods
- Response normalization to standard format

## Testing

Test your strategy carefully before going live:

```python
# Test with small position sizes first
config = TradingConfig(
    trading_pairs=["BTC-USD"],
    position_size_percent=1.0,  # Start with 1%
    max_positions=1
)

bot = TradingBot(adapter, config)
# Monitor closely when starting
bot.run(iterations=10)  # Run for 10 cycles only
```

## Support

- Robinhood API issues: Check `robinhood/py/README.md`
- Trading bot issues: Check `trading_bot/py/README.md`
- Integration issues: See examples or open an issue

## License

MIT License - See LICENSE file in repository root.
