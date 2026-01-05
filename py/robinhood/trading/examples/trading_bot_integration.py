"""
Example: Using Robinhood client with a trading bot.

This example shows how to integrate the Robinhood API client
with a simple trading bot that uses indicators.
"""
from robinhood.trading import RobinhoodClient, KeyManager
import time
from typing import List


class SimpleMovingAverage:
    """Calculate simple moving average."""
    
    def __init__(self, period: int = 20):
        self.period = period
        self.prices: List[float] = []
    
    def add_price(self, price: float):
        """Add a new price."""
        self.prices.append(price)
        if len(self.prices) > self.period:
            self.prices.pop(0)
    
    def get_value(self) -> float:
        """Get current SMA value."""
        if len(self.prices) < self.period:
            return 0.0
        return sum(self.prices) / len(self.prices)
    
    def is_ready(self) -> bool:
        """Check if enough data points."""
        return len(self.prices) >= self.period


class SimpleTradingBot:
    """Simple trading bot using moving average crossover strategy."""
    
    def __init__(self, client: RobinhoodClient, symbol: str = "BTC-USD"):
        """
        Initialize trading bot.
        
        Args:
            client: Robinhood API client
            symbol: Trading pair to trade
        """
        self.client = client
        self.symbol = symbol
        self.sma_short = SimpleMovingAverage(period=5)
        self.sma_long = SimpleMovingAverage(period=20)
        self.position = None
        self.paper_trading = True  # Safety flag
    
    def update_indicators(self):
        """Fetch current price and update indicators."""
        price = self.client.get_current_price(self.symbol)
        if price:
            self.sma_short.add_price(price)
            self.sma_long.add_price(price)
            return price
        return None
    
    def get_signal(self) -> str:
        """
        Generate trading signal based on strategy.
        
        Returns:
            'buy', 'sell', or 'hold'
        """
        if not (self.sma_short.is_ready() and self.sma_long.is_ready()):
            return 'hold'
        
        short_ma = self.sma_short.get_value()
        long_ma = self.sma_long.get_value()
        
        # Simple crossover strategy
        if short_ma > long_ma and self.position is None:
            return 'buy'
        elif short_ma < long_ma and self.position is not None:
            return 'sell'
        
        return 'hold'
    
    def execute_trade(self, signal: str):
        """
        Execute trade based on signal.
        
        Args:
            signal: Trading signal ('buy' or 'sell')
        """
        if self.paper_trading:
            # Paper trading - just log the action
            if signal == 'buy':
                price = self.client.get_current_price(self.symbol)
                self.position = {
                    'entry_price': price,
                    'quantity': 0.001,
                    'symbol': self.symbol
                }
                print(f"[PAPER] BUY {self.position['quantity']} {self.symbol} @ ${price:,.2f}")
            
            elif signal == 'sell' and self.position:
                price = self.client.get_current_price(self.symbol)
                profit = (price - self.position['entry_price']) * self.position['quantity']
                print(f"[PAPER] SELL {self.position['quantity']} {self.symbol} @ ${price:,.2f}")
                print(f"[PAPER] Profit: ${profit:,.2f}")
                self.position = None
        
        else:
            # Live trading - place real orders
            if signal == 'buy':
                order = self.client.place_market_order(
                    symbol=self.symbol,
                    side="buy",
                    asset_quantity=0.001
                )
                self.position = order
                print(f"✓ BUY order placed: {order['id']}")
            
            elif signal == 'sell' and self.position:
                order = self.client.place_market_order(
                    symbol=self.symbol,
                    side="sell",
                    asset_quantity=0.001
                )
                print(f"✓ SELL order placed: {order['id']}")
                self.position = None
    
    def run_iteration(self):
        """Run one iteration of the bot."""
        print(f"\n{'='*60}")
        print(f"Bot Iteration - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Update indicators
        current_price = self.update_indicators()
        
        if current_price:
            print(f"Current Price: ${current_price:,.2f}")
            
            # Show indicators if ready
            if self.sma_short.is_ready() and self.sma_long.is_ready():
                print(f"SMA(5): ${self.sma_short.get_value():,.2f}")
                print(f"SMA(20): ${self.sma_long.get_value():,.2f}")
                
                # Get signal
                signal = self.get_signal()
                print(f"Signal: {signal.upper()}")
                
                # Execute if not hold
                if signal != 'hold':
                    self.execute_trade(signal)
            else:
                print("Collecting data for indicators...")
        
        # Show position
        if self.position:
            if self.paper_trading:
                current = self.client.get_current_price(self.symbol)
                profit = (current - self.position['entry_price']) * self.position['quantity']
                print(f"\nOpen Position:")
                print(f"  Entry: ${self.position['entry_price']:,.2f}")
                print(f"  Current P&L: ${profit:,.2f}")
            else:
                print(f"\nOpen Position: Order ID {self.position.get('id')}")
    
    def start(self, interval_seconds: int = 60, iterations: int = 10):
        """
        Start the trading bot.
        
        Args:
            interval_seconds: Seconds between iterations
            iterations: Number of iterations (None for infinite)
        """
        print("\n🤖 Starting Trading Bot...")
        print(f"   Mode: {'PAPER TRADING' if self.paper_trading else 'LIVE TRADING'}")
        print(f"   Symbol: {self.symbol}")
        print(f"   Interval: {interval_seconds}s")
        print(f"   Iterations: {iterations if iterations else 'Infinite'}")
        print()
        
        try:
            count = 0
            while iterations is None or count < iterations:
                self.run_iteration()
                count += 1
                
                if iterations and count < iterations:
                    print(f"\nWaiting {interval_seconds} seconds...")
                    time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Bot stopped by user")


def main():
    """Run the trading bot example."""
    
    print("="*70)
    print("Robinhood API Client - Trading Bot Example")
    print("="*70)
    print()
    
    # Load client
    print("Loading Robinhood client...")
    manager = KeyManager()
    cipher_key = manager.load_cipher_key()
    client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)
    print("✓ Client loaded")
    print()
    
    # Create bot
    bot = SimpleTradingBot(client, symbol="BTC-USD")
    bot.paper_trading = True  # ALWAYS start with paper trading!
    
    print("📝 This is a DEMO trading bot using paper trading")
    print("   It uses a simple Moving Average crossover strategy")
    print("   No real trades will be executed")
    print()
    print("Strategy:")
    print("  • BUY when SMA(5) crosses above SMA(20)")
    print("  • SELL when SMA(5) crosses below SMA(20)")
    print()
    
    # Run for limited iterations
    bot.start(interval_seconds=10, iterations=30)
    
    print("\n" + "="*70)
    print("Trading bot example complete!")
    print("="*70)
    print()
    print("To create your own bot:")
    print("  1. Implement your strategy logic")
    print("  2. Test thoroughly in paper trading mode")
    print("  3. Use real indicators and ML models")
    print("  4. Add proper risk management")
    print("  5. Only then consider live trading")
    print()


if __name__ == "__main__":
    main()
