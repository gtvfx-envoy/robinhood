# Robinhood Crypto Trading API - Python Interface

A clean, secure Python interface for the Robinhood Crypto Trading API with encrypted credential storage and full endpoint coverage.

## Features

### 🔐 Secure Credential Management
- **File-based encryption** with separate cipher key
- **Password-based encryption** using PBKDF2
- **AES-256 encryption** via Fernet
- Never store keys in plain text

### 📡 Complete API Coverage
- **Account Management**: Get account details, buying power
- **Market Data**: Best bid/ask, estimated prices
- **Trading Pairs**: List available trading pairs
- **Holdings**: View your crypto holdings
- **Orders**: Place, cancel, and query orders
  - Market orders
  - Limit orders
  - Order history and status

### 🛡️ Built for Safety
- Proper Ed25519 signature generation
- Request signing and authentication
- Error handling and validation
- Type hints throughout

## Installation

### Requirements

```bash
pip install cryptography pynacl requests
```

### Dependencies

- `cryptography>=41.0.0` - For secure encryption
- `pynacl>=1.5.0` - For Ed25519 signing
- `requests>=2.31.0` - For HTTP requests

## Quick Start

### 1. Generate Key Pair

First, generate an Ed25519 key pair:

```bash
cd r:\repo\robinhood\py
python -m robinhood_trading.generate_keys
```

This will output:
- **Public Key** - Submit this to Robinhood when creating API credentials
- **Private Key** - Keep this secret and secure

### 2. Create API Credentials on Robinhood

1. Go to https://robinhood.com/account/crypto
2. Create a new API credential
3. Submit your public key
4. Save the API key you receive

### 3. Encrypt and Store Your Keys

```bash
python -m robinhood_trading.setup_keys
```

This interactive script will:
- Prompt for your API key
- Prompt for your private key
- Ask for encryption method (file-based or password-based)
- Securely encrypt and store your credentials

### 4. Use the Client

```python
from robinhood_trading import RobinhoodClient, KeyManager

# Load encrypted keys
manager = KeyManager()
cipher_key = manager.load_cipher_key()
client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)

# Get account details
account = client.get_account()
print(f"Account: {account['account_number']}")
print(f"Buying Power: ${account['buying_power']}")

# Get current price
price = client.get_current_price("BTC-USD")
print(f"BTC Price: ${price:.2f}")

# Get holdings
holdings = client.get_holdings()
for holding in holdings['results']:
    print(f"{holding['asset_code']}: {holding['total_quantity']}")
```

## Usage Examples

### Account Information

```python
# Get account details
account = client.get_account()
print(f"Buying Power: {account['buying_power']} {account['buying_power_currency']}")
print(f"Account Status: {account['status']}")
```

### Market Data

```python
# Get best bid/ask for multiple symbols
prices = client.get_best_bid_ask(["BTC-USD", "ETH-USD"])
for result in prices['results']:
    print(f"{result['symbol']}:")
    print(f"  Bid: ${result['bid_inclusive_of_buy_spread']}")
    print(f"  Ask: ${result['ask_inclusive_of_sell_spread']}")

# Get estimated price for a specific quantity
estimate = client.get_estimated_price(
    symbol="BTC-USD",
    side="ask",  # For buying
    quantity="0.1,1,2"  # Multiple quantities
)
for result in estimate['results']:
    print(f"Quantity: {result['quantity']}")
    print(f"Price: ${result['price']}")

# Helper method for current price
current_price = client.get_current_price("BTC-USD")
print(f"Current BTC price: ${current_price:.2f}")
```

### View Holdings

```python
# Get all holdings
holdings = client.get_holdings()
for holding in holdings['results']:
    asset = holding['asset_code']
    quantity = holding['total_quantity']
    available = holding['quantity_available_for_trading']
    print(f"{asset}: {quantity} (Available: {available})")

# Get specific assets
btc_eth = client.get_holdings(asset_codes=["BTC", "ETH"])

# Helper method for balance
btc_balance = client.get_balance("BTC")
print(f"BTC Balance: {btc_balance}")
```

### Trading Pairs

```python
# Get all trading pairs
pairs = client.get_trading_pairs()
for pair in pairs['results']:
    print(f"{pair['symbol']}: {pair['display_name']}")
    print(f"  Min order: {pair['min_order_size']}")
    print(f"  Max order: {pair['max_order_size']}")

# Get specific pairs
btc_pair = client.get_trading_pairs(symbols=["BTC-USD"])
```

### Place Orders

```python
# Market order
order = client.place_market_order(
    symbol="BTC-USD",
    side="buy",
    asset_quantity=0.001
)
print(f"Order ID: {order['id']}")
print(f"Status: {order['state']}")

# Limit order (with asset quantity)
limit_order = client.place_limit_order(
    symbol="BTC-USD",
    side="buy",
    limit_price=45000.00,
    asset_quantity=0.001
)

# Limit order (with quote amount in USD)
limit_order = client.place_limit_order(
    symbol="BTC-USD",
    side="buy",
    limit_price=45000.00,
    quote_amount=100.00  # $100 worth
)
```

### Manage Orders

```python
# Get all orders
orders = client.get_orders()
for order in orders['results']:
    print(f"{order['symbol']}: {order['side']} {order['state']}")

# Get orders with filters
recent_orders = client.get_orders(
    symbol="BTC-USD",
    state="filled",
    side="buy"
)

# Get specific order
order = client.get_order(order_id="order-uuid-here")
print(f"Order: {order['symbol']} - {order['state']}")

# Cancel an order
result = client.cancel_order(order_id="order-uuid-here")
print(result)
```

## API Reference

### RobinhoodClient

Main client for interacting with the Robinhood Crypto API.

#### Initialization

```python
# From KeyManager
client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)

# Direct initialization
client = RobinhoodClient(api_key="your-api-key", private_key_base64="your-private-key")
```

#### Methods

**Account**
- `get_account()` - Get account details

**Market Data**
- `get_best_bid_ask(symbols=None)` - Get best bid/ask prices
- `get_estimated_price(symbol, side, quantity)` - Get estimated price
- `get_current_price(symbol)` - Helper: get current mid price

**Trading Pairs**
- `get_trading_pairs(symbols=None, limit=None, cursor=None)` - List trading pairs

**Holdings**
- `get_holdings(asset_codes=None, limit=None, cursor=None)` - Get holdings
- `get_balance(asset_code)` - Helper: get balance for specific asset

**Orders**
- `get_orders(**filters)` - List orders with filters
- `get_order(order_id)` - Get specific order
- `place_market_order(symbol, side, asset_quantity, client_order_id=None)` - Place market order
- `place_limit_order(symbol, side, limit_price, asset_quantity=None, quote_amount=None, client_order_id=None)` - Place limit order
- `cancel_order(order_id)` - Cancel order

### KeyManager

Handles secure encryption and storage of API credentials.

```python
manager = KeyManager(
    key_file="robinhood_keys.enc",
    cipher_key_file="robinhood_cipher.key"
)

# File-based encryption
cipher_key = manager.generate_cipher_key()
manager.save_cipher_key(cipher_key)
manager.encrypt_and_save_keys(api_key, private_key, cipher_key)
credentials = manager.load_encrypted_keys(cipher_key)

# Password-based encryption
manager.save_with_password_v2(api_key, private_key, password="your-password")
credentials = manager.load_with_password(password="your-password")
```

## Security Best Practices

1. **Never commit encrypted key files to version control**
   - Add to `.gitignore`: `*.enc`, `*.key`

2. **Keep your private key secret**
   - Never share it
   - Robinhood will never ask for it

3. **Use strong passwords for password-based encryption**
   - At least 12 characters
   - Mix of letters, numbers, symbols

4. **Backup your encrypted keys securely**
   - Store in a secure location
   - Consider using a password manager

5. **Rotate keys regularly**
   - Generate new keys periodically
   - Delete old keys from Robinhood portal

## Rate Limiting

Robinhood API has rate limits:
- **100 requests per minute** per user account
- **300 requests per minute** in bursts

The client does not automatically handle rate limiting. Consider:
- Adding delays between requests
- Implementing exponential backoff
- Caching responses when appropriate

## Error Handling

The client raises exceptions for HTTP errors:

```python
try:
    order = client.place_market_order("BTC-USD", "buy", 0.001)
except requests.exceptions.HTTPError as e:
    print(f"HTTP Error: {e}")
    # Handle error
except requests.exceptions.RequestException as e:
    print(f"Request Error: {e}")
    # Handle error
```

## Integration with Trading Bots

This client is designed to work seamlessly with trading bots that use technical indicators and machine learning:

```python
from robinhood_trading import RobinhoodClient, KeyManager

# Initialize client
manager = KeyManager()
cipher_key = manager.load_cipher_key()
client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)

# Use with your trading bot
class TradingBot:
    def __init__(self, client):
        self.client = client
    
    def get_market_data(self, symbol):
        """Get current market data."""
        return self.client.get_current_price(symbol)
    
    def execute_trade(self, symbol, side, quantity):
        """Execute a trade based on strategy."""
        order = self.client.place_market_order(symbol, side, quantity)
        return order

bot = TradingBot(client)
```

## Project Structure

```
robinhood_trading/
├── __init__.py           # Package initialization
├── key_manager.py        # Secure key storage
├── client.py             # API client
├── setup_keys.py         # Interactive key setup
└── generate_keys.py      # Key pair generation
```

## Comparison with Existing Code

This new interface improves upon existing code by:

1. **Security**: Encrypted key storage vs plain text JSON
2. **Clean API**: Simple method calls vs manual request building
3. **Type Safety**: Type hints throughout
4. **Error Handling**: Proper exception handling
5. **Documentation**: Comprehensive docstrings and examples
6. **Maintainability**: Modular structure, easy to extend

## Troubleshooting

### "Signature verification failed"
- Check that your private key matches the public key submitted to Robinhood
- Ensure timestamp is correct (system time synchronized)
- Verify API key format

### "Invalid API key"
- Confirm API key is correct
- Check if key has been disabled on Robinhood
- Ensure key is properly encrypted/decrypted

### "Rate limit exceeded"
- Slow down requests
- Implement exponential backoff
- Cache responses when possible

## API Documentation

Official Robinhood Crypto API documentation:
https://docs.robinhood.com/crypto/trading/

## License

This interface is part of the robinhood trading project.

## Disclaimer

**This software is for educational purposes only. Cryptocurrency trading carries significant risk.**

- Test thoroughly before live trading
- Understand the risks
- Never trade more than you can afford to lose
- This is not financial advice
- Past performance does not guarantee future results

## Support

For issues specific to:
- **This interface**: Review examples and documentation
- **Robinhood API**: Check official docs at https://docs.robinhood.com
- **Trading strategies**: This interface provides API access only

## Contributing

Contributions welcome! Areas for improvement:
- Additional helper methods
- Websocket support for real-time data
- Better error messages
- More examples

## Future Enhancements

Planned features:
- Websocket streaming for real-time prices
- Advanced order types (stop-loss, stop-limit)
- Portfolio analytics
- Transaction history export
- Paper trading mode
