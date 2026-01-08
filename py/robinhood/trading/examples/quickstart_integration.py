"""Quick Start: Robinhood + Trading Bot Integration

This is a minimal example showing how to connect Robinhood to the trading_bot.

"""

from robinhood.trading import RobinhoodClient, RobinhoodExchangeAdapter
from trading_bot import TradingConfig, TradingStrategy
import os


def main():
    # 1. Setup Robinhood client directly with API credentials
    print("Initializing Robinhood client...")
    
    # Get credentials from environment variables (recommended)
    api_key = os.getenv("ROBINHOOD_API_KEY")
    private_key = os.getenv("ROBINHOOD_PRIVATE_KEY")
    
    if not api_key or not private_key:
        print("❌ Please set environment variables:")
        print("   ROBINHOOD_API_KEY")
        print("   ROBINHOOD_PRIVATE_KEY")
        print("\nOr pass them directly:")
        print('   client = RobinhoodClient("your-api-key", "your-private-key-base64")')
        return
    
    # Create client directly - no password needed!
    client = RobinhoodClient(api_key, private_key)
    
    # 2. Create adapter
    adapter = RobinhoodExchangeAdapter(client)
    
    # 3. Check connection
    print(f"Buying Power: ${adapter.get_buying_power():,.2f}")
    print(f"Holdings: {adapter.get_holdings()}")
    
    # 4. Get current prices
    for symbol in ["BTC-USD", "ETH-USD"]:
        price = adapter.get_current_price(symbol)
        print(f"{symbol}: ${price:,.2f}")
    
    # 5. Configure trading strategy with paper trading
    config = TradingConfig(
        trading_pairs=["BTC-USD"],
        position_size_percent=5.0,
        stop_loss_percent=2.0,
        take_profit_percent=5.0,
        paper_trading=True,  # Start with paper trading to test
        paper_trading_balance=10000.0  # $10,000 simulated balance
    )
    
    # 6. Use with trading bot (note: adapter first, then config)
    from trading_bot import TradingBot
    
    bot = TradingBot(adapter, config)  # adapter first!
    
    print("\n✓ Integration successful!")
    print("\nNext steps:")
    print("  1. Test with paper trading: bot.run(iterations=10, paper_trading=True)")
    print("  2. Once confident, switch to live: config.paper_trading = False")
    print("  3. Or use adapter methods directly for manual trading")
    print("\n⚠️ Paper trading mode simulates trades without using real money")


if __name__ == "__main__":
    main()
