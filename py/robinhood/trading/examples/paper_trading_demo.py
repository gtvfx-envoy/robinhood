"""Paper Trading Example: Test your strategy without risking real money.

This example demonstrates how to use paper trading mode to test your trading
strategy with simulated trades before going live.
"""

import os
from robinhood.trading import RobinhoodClient, RobinhoodExchangeAdapter
from trading_bot import TradingBot, TradingConfig


def main():
    """Run trading bot in paper trading mode."""
    
    print("=" * 70)
    print("Paper Trading Example")
    print("=" * 70)
    print()
    
    # 1. Setup Robinhood client
    api_key = os.getenv("ROBINHOOD_API_KEY")
    private_key = os.getenv("ROBINHOOD_PRIVATE_KEY")
    
    if not api_key or not private_key:
        print("❌ Please set environment variables:")
        print("   ROBINHOOD_API_KEY")
        print("   ROBINHOOD_PRIVATE_KEY")
        return
    
    client = RobinhoodClient(api_key, private_key)
    adapter = RobinhoodExchangeAdapter(client)
    
    # 2. Create configuration with paper trading enabled
    config = TradingConfig(
        trading_pairs=["BTC-USD", "ETH-USD"],
        position_size_percent=10.0,  # Use 10% of balance per trade
        max_positions=2,
        stop_loss_percent=3.0,
        take_profit_percent=5.0,
        ml_enabled=True,
        paper_trading=True,  # 🧪 Enable paper trading
        paper_trading_balance=10000.0  # Start with $10,000 virtual money
    )
    
    # 3. Initialize trading bot
    bot = TradingBot(adapter, config)
    
    print("🧪 Paper Trading Mode Enabled")
    print(f"   Virtual Balance: ${config.paper_trading_balance:,.2f}")
    print(f"   Trading Pairs: {', '.join(config.trading_pairs)}")
    print(f"   Position Size: {config.position_size_percent}%")
    print()
    print("This bot will simulate trades without executing real orders.")
    print("Perfect for testing your strategy!")
    print()
    
    # 4. Run bot with limited iterations to test
    print("Running 10 iterations in paper trading mode...")
    print("Press Ctrl+C to stop early")
    print()
    
    try:
        bot.run(iterations=10)
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
    
    print()
    print("=" * 70)
    print("Paper Trading Summary")
    print("=" * 70)
    print(f"Final Virtual Balance: ${bot.paper_balance:,.2f}")
    print(f"Virtual Equity in Positions: ${bot.paper_equity:,.2f}")
    print(f"Total Virtual Portfolio: ${bot.paper_balance + bot.paper_equity:,.2f}")
    print()
    
    # Calculate performance
    initial = config.paper_trading_balance
    final = bot.paper_balance + bot.paper_equity
    pnl = final - initial
    pnl_pct = (pnl / initial) * 100
    
    print(f"P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
    print()
    
    if pnl > 0:
        print("📈 Profitable! Consider running live with small position sizes.")
    else:
        print("📉 Strategy needs improvement. Keep testing in paper mode.")
    
    print()
    print("To switch to live trading:")
    print("  1. Review your strategy carefully")
    print("  2. Set config.paper_trading = False")
    print("  3. Start with VERY small position_size_percent (1-2%)")
    print("  4. Monitor closely!")


if __name__ == "__main__":
    main()
