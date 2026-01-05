"""
Example: Basic usage of the Robinhood API client.

This example demonstrates basic operations like getting account info,
checking prices, and viewing holdings.
"""
from robinhood.trading import RobinhoodClient, KeyManager


def main():
    """Run basic API examples."""
    
    print("="*70)
    print("Robinhood API Client - Basic Example")
    print("="*70)
    print()
    
    # Load client from encrypted keys
    print("Loading Robinhood client...")
    manager = KeyManager()
    cipher_key = manager.load_cipher_key()
    client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)
    print("✓ Client loaded")
    print()
    
    # Get account information
    print("-" * 70)
    print("ACCOUNT INFORMATION")
    print("-" * 70)
    
    account = client.get_account()
    print(f"Account Number: {account['account_number']}")
    print(f"Status: {account['status']}")
    print(f"Buying Power: ${account['buying_power']} {account['buying_power_currency']}")
    print()
    
    # Get market prices
    print("-" * 70)
    print("MARKET PRICES")
    print("-" * 70)
    
    symbols = ["BTC-USD", "ETH-USD", "DOGE-USD"]
    
    for symbol in symbols:
        price = client.get_current_price(symbol)
        if price:
            print(f"{symbol}: ${price:,.2f}")
    print()
    
    # Get detailed bid/ask
    print("-" * 70)
    print("BID/ASK SPREADS")
    print("-" * 70)
    
    prices = client.get_best_bid_ask(["BTC-USD"])
    for result in prices.get('results', []):
        print(f"{result['symbol']}:")
        print(f"  Price: ${float(result['price']):,.2f}")
        print(f"  Bid: ${float(result['bid_inclusive_of_sell_spread']):,.2f}")
        print(f"  Ask: ${float(result['ask_inclusive_of_buy_spread']):,.2f}")
        print(f"  Buy Spread: {float(result['buy_spread']):.2%}")
        print(f"  Sell Spread: {float(result['sell_spread']):.2%}")
    print()
    
    # Get holdings
    print("-" * 70)
    print("YOUR HOLDINGS")
    print("-" * 70)
    
    holdings = client.get_holdings()
    
    if holdings.get('results'):
        for holding in holdings['results']:
            asset = holding['asset_code']
            total = float(holding['total_quantity'])
            available = float(holding['quantity_available_for_trading'])
            
            if total > 0:
                print(f"{asset}:")
                print(f"  Total: {total:.8f}")
                print(f"  Available: {available:.8f}")
                
                # Get current value
                if asset != 'USD':
                    symbol = f"{asset}-USD"
                    price = client.get_current_price(symbol)
                    if price:
                        value = total * price
                        print(f"  Value: ${value:,.2f}")
                print()
    else:
        print("No holdings found")
        print()
    
    # Get trading pairs info
    print("-" * 70)
    print("TRADING PAIRS INFO")
    print("-" * 70)
    
    pairs = client.get_trading_pairs(symbols=["BTC-USD"])
    if pairs.get('results'):
        for pair in pairs['results']:
            print(f"{pair['symbol']}:")
            print(f"  Asset: {pair.get('asset_currency', {}).get('code', 'N/A')}")
            print(f"  Quote: {pair.get('quote_currency', {}).get('code', 'N/A')}")
            print(f"  Min Order: {pair.get('min_order_size', 'N/A')}")
            print(f"  Max Order: {pair.get('max_order_size', 'N/A')}")
            print(f"  Status: {pair.get('trading_state', 'N/A')}")
    print()
    
    print("="*70)
    print("Example complete!")
    print("="*70)


if __name__ == "__main__":
    main()
