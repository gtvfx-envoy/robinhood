"""
Quick Reference: Robinhood + Trading Bot
=========================================

SETUP (Choose one)
------------------
# Option 1: Direct (Simple)
from robinhood.trading import RobinhoodClient, RobinhoodExchangeAdapter
import os

api_key = os.getenv("ROBINHOOD_API_KEY")
private_key = os.getenv("ROBINHOOD_PRIVATE_KEY")
client = RobinhoodClient(api_key, private_key)
adapter = RobinhoodExchangeAdapter(client)

# Option 2: Encrypted Storage (More Secure)
from robinhood.trading import RobinhoodClient, KeyManager, RobinhoodExchangeAdapter

manager = KeyManager()
client = RobinhoodClient.from_key_manager(manager, password="your_password")
adapter = RobinhoodExchangeAdapter(client)


ACCOUNT INFO
------------
# Balances
balances = adapter.get_account_balance()  # {'USD': 10000.0, 'BTC': 0.5}

# Buying power
power = adapter.get_buying_power()  # 10000.0

# Holdings
holdings = adapter.get_holdings()  # {'BTC': 0.5, 'ETH': 2.0}


MARKET DATA
-----------
# Current price
price = adapter.get_current_price("BTC-USD")  # 50000.0

# Historical (NOT IMPLEMENTED - need data provider)
# df = adapter.get_historical_candles("BTC-USD", start, end, "1h")


ORDERS
------
# Market order
order = adapter.place_market_order("BTC-USD", "buy", 0.001)
# Returns: {'id': 'abc123', 'status': 'filled', 'filled_quantity': 0.001}

# Limit order
order = adapter.place_limit_order("ETH-USD", "sell", 0.1, 3500.0)

# Check status
status = adapter.get_order_status(order['id'])

# Cancel
success = adapter.cancel_order(order['id'])  # True/False

# Open orders
orders = adapter.get_open_orders()  # All open
orders = adapter.get_open_orders("BTC-USD")  # Specific pair


TRADING BOT
-----------
from trading_bot import TradingBot, TradingConfig

# Paper trading mode (simulates trades)
config = TradingConfig(
    trading_pairs=["BTC-USD", "ETH-USD"],
    position_size_percent=5.0,
    stop_loss_percent=3.0,
    take_profit_percent=5.0,
    ml_enabled=True,
    paper_trading=True,  # Enable simulation mode
    paper_trading_balance=10000.0  # Starting virtual balance
)

# Note: adapter first, then config
bot = TradingBot(adapter, config)

# Test with paper trading first
bot.run(iterations=10, paper_trading=True)

# Switch to live trading when ready
config.paper_trading = False
bot.run()


FEATURES
--------
✅ Account balance & buying power
✅ Current prices
✅ Market & limit orders
✅ Order management
✅ Holdings tracking
✅ Paper trading mode (simulated trades)
⚠️  Historical data (need external provider)
❌ Stop-loss orders (not supported by Robinhood)


USAGE
-----
# Test with paper trading (simulated)
config.paper_trading = True
bot.run(iterations=10, paper_trading=True)

# Run live with limited cycles
config.paper_trading = False
bot.run(iterations=10)

# Or run continuously (Ctrl+C to stop)
bot.run()

# ⚠️ ALWAYS test with paper_trading=True first!
# Then start live with small position sizes
"""
