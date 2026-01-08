"""
Simple Example: Direct Robinhood Client Initialization

No password needed - just use your API credentials directly.
"""

from robinhood.trading import RobinhoodClient, RobinhoodExchangeAdapter
from trading_bot import TradingConfig
import os

# ============================================================================
# Method 1: From Environment Variables (Recommended)
# ============================================================================

print("Method 1: Environment Variables")
print("=" * 70)

# Set these in your environment:
# export ROBINHOOD_API_KEY="your-api-key"
# export ROBINHOOD_PRIVATE_KEY="your-base64-private-key"

api_key = os.getenv("ROBINHOOD_API_KEY")
private_key = os.getenv("ROBINHOOD_PRIVATE_KEY")

if api_key and private_key:
    # Direct initialization - no password!
    client = RobinhoodClient(api_key, private_key)
    adapter = RobinhoodExchangeAdapter(client)
    
    print("✓ Client initialized")
    print(f"  Buying Power: ${adapter.get_buying_power():,.2f}")
else:
    print("Set ROBINHOOD_API_KEY and ROBINHOOD_PRIVATE_KEY environment variables")

print()

# ============================================================================
# Method 2: Hardcoded (Not Recommended - for testing only)
# ============================================================================

print("Method 2: Direct Values (Testing Only)")
print("=" * 70)

# DON'T commit these to git!
MY_API_KEY = "your-api-key-here"
MY_PRIVATE_KEY = "your-base64-private-key-here"

if MY_API_KEY != "your-api-key-here":
    client = RobinhoodClient(MY_API_KEY, MY_PRIVATE_KEY)
    adapter = RobinhoodExchangeAdapter(client)
    print("✓ Client initialized")
else:
    print("Replace MY_API_KEY and MY_PRIVATE_KEY with your actual credentials")

print()

# ============================================================================
# Method 3: From Config File
# ============================================================================

print("Method 3: Config File")
print("=" * 70)

import json
from pathlib import Path

config_file = Path.home() / ".robinhood" / "config.json"

if config_file.exists():
    with open(config_file) as f:
        config = json.load(f)
    
    client = RobinhoodClient(
        config["api_key"],
        config["private_key"]
    )
    adapter = RobinhoodExchangeAdapter(client)
    print("✓ Client initialized from config file")
else:
    print(f"Create {config_file} with your credentials:")
    print('{')
    print('  "api_key": "your-api-key",')
    print('  "private_key": "your-base64-private-key"')
    print('}')

print()

# ============================================================================
# Use with Trading Bot
# ============================================================================

print("Using with Trading Bot")
print("=" * 70)

if 'adapter' in locals():
    from trading_bot import TradingBot
    
    config = TradingConfig(
        trading_pairs=["BTC-USD", "ETH-USD"],
        position_size_percent=5.0
    )
    
    # Pass the adapter to the trading bot (adapter first!)
    # bot = TradingBot(adapter, config)
    # bot.run()
    
    print("✓ Ready to use with trading bot")
    print(f"  Current BTC price: ${adapter.get_current_price('BTC-USD'):,.2f}")
