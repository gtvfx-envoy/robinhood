"""
Complete Working Example: Robinhood + Trading Bot

This shows the correct way to initialize and use the trading bot.
"""

from robinhood.trading import RobinhoodClient, RobinhoodExchangeAdapter, get_keys
from trading_bot import TradingBot, TradingConfig

# Step 1: Get your API credentials
# This loads from SERVICE_ROOT/robinhood.json
private_key, public_key, api_key = get_keys()
print("✓ Credentials loaded")

# Step 2: Create Robinhood client directly (no password!)
client = RobinhoodClient(api_key, private_key)
print("✓ Client initialized")

# Step 3: Create adapter
adapter = RobinhoodExchangeAdapter(client)
print(f"✓ Adapter created (Buying Power: ${adapter.get_buying_power():,.2f})")

# Step 4: Configure trading bot
config = TradingConfig(
    trading_pairs=["BTC-USD"],
    position_size_percent=5.0,
    stop_loss_percent=2.0,
    take_profit_percent=5.0
)
print("✓ Config created")

# Step 5: Initialize bot
# IMPORTANT: adapter first, then config!
bot = TradingBot(adapter, config)
print("✓ Bot initialized")

print("\n" + "="*70)
print("SUCCESS! Bot is ready to use.")
print("="*70)
print("\nNext steps:")
print("  # Start with limited cycles for testing")
print("  bot.run(iterations=5)  # Run 5 cycles then stop")
print("  ")
print("  # Or run continuously")
print("  bot.run()  # Press Ctrl+C to stop")
print("\nOr use adapter methods directly:")
print("  adapter.get_current_price('BTC-USD')")
print("  adapter.place_market_order('BTC-USD', 'buy', 0.001)")
print("\n⚠️  Bot will execute REAL trades with your account!")
