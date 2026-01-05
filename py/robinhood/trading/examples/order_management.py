"""
Example: Placing and managing orders.

This example demonstrates how to place different types of orders
and query order status.

⚠️  WARNING: This example uses PAPER TRADING simulation.
Set LIVE_TRADING = True only after thorough testing!
"""
from robinhood.trading import RobinhoodClient, KeyManager


# SAFETY FLAG - Change to True only when ready for live trading!
LIVE_TRADING = False


def main():
    """Run order placement examples."""
    
    print("="*70)
    print("Robinhood API Client - Order Management Example")
    print("="*70)
    print()
    
    if LIVE_TRADING:
        print("⚠️  LIVE TRADING MODE - REAL MONEY AT RISK!")
    else:
        print("📝 PAPER TRADING MODE - No real trades will be executed")
        print("   (This example demonstrates the API calls)")
    print()
    
    # Load client
    print("Loading Robinhood client...")
    manager = KeyManager()
    cipher_key = manager.load_cipher_key()
    client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)
    print("✓ Client loaded")
    print()
    
    # Example 1: Get estimated price before ordering
    print("-" * 70)
    print("1. GET ESTIMATED PRICE")
    print("-" * 70)
    
    symbol = "BTC-USD"
    quantity = "0.001"
    
    print(f"Getting estimated price for {quantity} BTC...")
    estimate = client.get_estimated_price(
        symbol=symbol,
        side="ask",  # ask for buying
        quantity=quantity
    )
    
    if estimate.get('results'):
        result = estimate['results'][0]
        print(f"Quantity: {result['quantity']}")
        print(f"Estimated Price: ${float(result['price']):,.2f}")
        print(f"Total Cost: ${float(result['total_cost']):,.2f}")
    print()
    
    # Example 2: Place a market order (paper trading)
    print("-" * 70)
    print("2. PLACE MARKET ORDER (DEMO)")
    print("-" * 70)
    
    if not LIVE_TRADING:
        print("Simulating market order...")
        print(f"  Symbol: {symbol}")
        print(f"  Side: buy")
        print(f"  Quantity: {quantity}")
        print()
        print("To execute for real, set LIVE_TRADING = True")
        print("Example code:")
        print("""
        order = client.place_market_order(
            symbol="BTC-USD",
            side="buy",
            asset_quantity=0.001
        )
        print(f"Order ID: {order['id']}")
        print(f"Status: {order['state']}")
        """)
    else:
        # Real order placement
        print("⚠️  Placing REAL market order...")
        confirm = input("Type 'YES' to confirm: ")
        
        if confirm == "YES":
            order = client.place_market_order(
                symbol=symbol,
                side="buy",
                asset_quantity=float(quantity)
            )
            
            print(f"✓ Order placed!")
            print(f"  Order ID: {order['id']}")
            print(f"  Status: {order['state']}")
            print(f"  Side: {order['side']}")
            print(f"  Symbol: {order['symbol']}")
        else:
            print("Order cancelled by user")
    print()
    
    # Example 3: Place a limit order (paper trading)
    print("-" * 70)
    print("3. PLACE LIMIT ORDER (DEMO)")
    print("-" * 70)
    
    limit_price = 45000.00  # Example limit price
    
    if not LIVE_TRADING:
        print("Simulating limit order...")
        print(f"  Symbol: {symbol}")
        print(f"  Side: buy")
        print(f"  Limit Price: ${limit_price:,.2f}")
        print(f"  Quantity: {quantity}")
        print()
        print("Example code:")
        print(f"""
        order = client.place_limit_order(
            symbol="{symbol}",
            side="buy",
            limit_price={limit_price},
            asset_quantity={quantity}
        )
        """)
    print()
    
    # Example 4: Query orders
    print("-" * 70)
    print("4. QUERY RECENT ORDERS")
    print("-" * 70)
    
    print("Fetching recent orders...")
    orders = client.get_orders(limit=5)
    
    if orders.get('results'):
        print(f"Found {len(orders['results'])} recent orders:")
        print()
        
        for order in orders['results']:
            print(f"Order ID: {order['id']}")
            print(f"  Symbol: {order['symbol']}")
            print(f"  Side: {order['side']}")
            print(f"  Type: {order['type']}")
            print(f"  State: {order['state']}")
            print(f"  Created: {order['created_at']}")
            print()
    else:
        print("No recent orders found")
    print()
    
    # Example 5: Get specific order (demo)
    print("-" * 70)
    print("5. GET SPECIFIC ORDER (DEMO)")
    print("-" * 70)
    
    print("Example code to get a specific order:")
    print("""
    order_id = "your-order-id-here"
    order = client.get_order(order_id)
    
    print(f"Order Status: {order['state']}")
    print(f"Filled Quantity: {order['filled_asset_quantity']}")
    print(f"Average Price: {order['average_price']}")
    """)
    print()
    
    # Example 6: Cancel order (demo)
    print("-" * 70)
    print("6. CANCEL ORDER (DEMO)")
    print("-" * 70)
    
    print("Example code to cancel an open order:")
    print("""
    order_id = "your-order-id-here"
    result = client.cancel_order(order_id)
    print(result)
    """)
    print()
    
    print("="*70)
    print("Order management example complete!")
    print("="*70)
    print()
    print("Remember:")
    print("  • Always test with small amounts first")
    print("  • Check order status after placement")
    print("  • Be aware of market volatility")
    print("  • Monitor rate limits")
    print()


if __name__ == "__main__":
    main()
