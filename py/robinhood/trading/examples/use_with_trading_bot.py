"""Example: Using Robinhood with the trading_bot framework.

This example demonstrates how to integrate Robinhood's API with the
generic trading_bot framework using the RobinhoodExchangeAdapter.

The adapter allows you to use all of trading_bot's features (technical
indicators, ML predictions, strategy generation) with your Robinhood account.

"""

from robinhood.trading import RobinhoodClient, RobinhoodExchangeAdapter
from trading_bot import TradingBot, TradingConfig
import os
import sys


def main():
    """Run the trading bot with Robinhood."""
    
    print("=" * 70)
    print("Trading Bot - Robinhood Integration")
    print("=" * 70)
    
    # ===== Step 1: Setup Robinhood Client =====
    print("\n[1/4] Initializing Robinhood client...")
    
    # Option 1: From environment variables (recommended for security)
    api_key = os.getenv("ROBINHOOD_API_KEY")
    private_key = os.getenv("ROBINHOOD_PRIVATE_KEY")
    
    if not api_key or not private_key:
        print("\n❌ Missing credentials!")
        print("\nSet environment variables:")
        print("  ROBINHOOD_API_KEY=your-api-key")
        print("  ROBINHOOD_PRIVATE_KEY=your-private-key-base64")
        print("\nOr use KeyManager for encrypted storage (see INTEGRATION.md)")
        sys.exit(1)
    
    try:
        # Create client directly - no password needed!
        client = RobinhoodClient(api_key, private_key)
        print("✓ Client initialized")
        
    except Exception as e:
        print(f"✗ Error initializing client: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error loading credentials: {e}")
        sys.exit(1)
    
    # ===== Step 2: Create Exchange Adapter =====
    print("\n[2/4] Creating exchange adapter...")
    adapter = RobinhoodExchangeAdapter(client)
    
    # Verify connection
    try:
        buying_power = adapter.get_buying_power()
        print(f"✓ Connected to Robinhood")
        print(f"  Buying Power: ${buying_power:,.2f}")
        
        holdings = adapter.get_holdings()
        if holdings:
            print(f"  Current Holdings:")
            for asset, qty in holdings.items():
                print(f"    {asset}: {qty}")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    
    # ===== Step 3: Configure Trading Bot =====
    print("\n[3/4] Configuring trading bot...")
    
    config = TradingConfig(
        # Trading pairs
        trading_pairs=["BTC-USD", "ETH-USD"],
        
        # Position sizing
        position_size_percent=5.0,  # Use 5% of buying power per trade
        max_positions=2,
        
        # Risk management
        stop_loss_percent=3.0,      # 3% stop loss
        take_profit_percent=5.0,    # 5% take profit
        trailing_stop_percent=2.0,  # 2% trailing stop
        max_daily_loss_percent=10.0,
        
        # Technical indicators
        rsi_period=14,
        rsi_oversold=30,
        rsi_overbought=70,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        ema_short=12,
        ema_long=26,
        
        # ML Configuration
        ml_enabled=True,
        ml_confidence_threshold=0.65,
        ml_model_type='random_forest',
        
        # Strategy
        min_signal_agreement=2,  # Require 2+ indicators to agree
        
        # Data
        lookback_window=100,
        candle_granularity='1h',
        refresh_interval=300  # Check every 5 minutes
    )
    
    print("✓ Configuration created")
    print(f"  Pairs: {', '.join(config.trading_pairs)}")
    print(f"  Position Size: {config.position_size_percent}%")
    print(f"  ML Enabled: {config.ml_enabled}")
    
    # ===== Step 4: Initialize Trading Bot =====
    print("\n[4/4] Initializing trading bot...")
    
    try:
        # Note: adapter first, then config
        bot = TradingBot(adapter, config)
        print("✓ Trading bot initialized")
        
    except Exception as e:
        print(f"✗ Failed to initialize bot: {e}")
        sys.exit(1)
    
    # ===== Main Trading Loop =====
    print("\n" + "=" * 70)
    print("TRADING BOT ACTIVE")
    print("=" * 70)
    print("\nPress Ctrl+C to stop\n")
    
    # Warning about live trading
    print("⚠️  LIVE TRADING MODE - Real money at risk!\n")
    confirm = input("Type 'START' to begin trading: ")
    if confirm != "START":
        print("Cancelled.")
        sys.exit(0)
    
    try:
        while True:
            print(f"\n[{bot._get_timestamp()}] Analyzing markets...")
            
            for symbol in config.trading_pairs:
                try:
                    # Get current price
                    price = adapter.get_current_price(symbol)
                    if not price:
                        print(f"  {symbol}: No price data available")
                        continue
                    
                    print(f"  {symbol}: ${price:,.2f}")
                    
                    # In a real implementation, you would:
                    # 1. Fetch historical data (need to implement get_historical_candles)
                    # 2. Calculate technical indicators
                    # 3. Generate ML predictions
                    # 4. Use strategy to generate signals
                    # 5. Execute trades based on signals
                    
                    # For now, just monitor
                    holdings = adapter.get_holdings()
                    if symbol.split('-')[0] in holdings:
                        qty = holdings[symbol.split('-')[0]]
                        value = qty * price
                        print(f"    Position: {qty:.8f} (${value:,.2f})")
                    
                except Exception as e:
                    print(f"  {symbol}: Error - {e}")
            
            # Check open orders
            open_orders = adapter.get_open_orders()
            if open_orders:
                print(f"\n  Open Orders: {len(open_orders)}")
                for order in open_orders:
                    print(f"    {order['side'].upper()} {order['symbol']} "
                          f"{order['quantity']} @ {order.get('price', 'MARKET')}")
            
            # Sleep until next check
            import time
            time.sleep(config.refresh_interval)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("Trading bot stopped")
        print("=" * 70)


def show_balance():
    """Quick script to show account balance."""
    manager = KeyManager()
    password = input("Enter your key storage password: ")
    client = RobinhoodClient.from_key_manager(manager, password=password)
    adapter = RobinhoodExchangeAdapter(client)
    
    print("\n" + "=" * 70)
    print("Account Balance")
    print("=" * 70)
    
    balances = adapter.get_account_balance()
    
    for asset, amount in sorted(balances.items()):
        if asset == 'USD':
            print(f"  {asset}: ${amount:,.2f}")
        else:
            price = adapter.get_current_price(f"{asset}-USD")
            if price:
                value = amount * price
                print(f"  {asset}: {amount:.8f} (${value:,.2f} @ ${price:,.2f})")
            else:
                print(f"  {asset}: {amount:.8f}")
    
    total_usd = balances.get('USD', 0)
    for asset, amount in balances.items():
        if asset != 'USD':
            price = adapter.get_current_price(f"{asset}-USD")
            if price:
                total_usd += amount * price
    
    print(f"\n  Total Value: ${total_usd:,.2f}")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "balance":
        show_balance()
    else:
        main()
