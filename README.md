# Robinhood Crypto Trading Repository

Python interface and trading tools for Robinhood Crypto Trading API.

## Project Structure

### `/py/robinhood_trading` - Clean API Interface (NEW ✨)

A professional Python interface to the Robinhood Crypto Trading API with:
- **Secure encrypted credential storage**
- **Complete API endpoint coverage**
- **Clean, intuitive methods**
- **Ready for trading bot integration**

**[View Full Documentation →](py/robinhood_trading/README.md)**

Quick start:
```python
from robinhood_trading import RobinhoodClient, KeyManager

# Load encrypted credentials
manager = KeyManager()
cipher_key = manager.load_cipher_key()
client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)

# Get current price
price = client.get_current_price("BTC-USD")
print(f"BTC: ${price:,.2f}")

# Place order
order = client.place_market_order("BTC-USD", "buy", 0.001)
```

### `/crypto_trading_bot` - Legacy Trading Bot

Original trading bot implementation with:
- Historical price aggregation
- Machine learning integration
- Real-time tracking
- Performance metrics

### `/py/robinhood` - Utility Scripts

Various utility scripts and interfaces:
- Key generation
- Example implementations
- Trading strategies (Bollinger Bands, Momentum)

## Getting Started

### 1. Install Dependencies

```bash
cd py/robinhood_trading
pip install -r requirements.txt
```

### 2. Generate API Keys

```bash
# Generate Ed25519 key pair
python -m robinhood_trading.generate_keys

# Copy public key and create API credential at:
# https://robinhood.com/account/crypto
```

### 3. Setup Encrypted Storage

```bash
# Encrypt and store your credentials
python -m robinhood_trading.setup_keys
```

### 4. Start Trading

```python
# See examples/basic_usage.py for complete examples
from robinhood_trading import RobinhoodClient, KeyManager

manager = KeyManager()
cipher_key = manager.load_cipher_key()
client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)

# Your trading code here...
```

## Features

### Secure Credential Management
- AES-256 encryption via Fernet
- File-based or password-based encryption
- Never store keys in plain text

### Complete API Coverage
- **Account**: Get account details and buying power
- **Market Data**: Best bid/ask, estimated prices, current prices
- **Trading Pairs**: List and query available pairs
- **Holdings**: View crypto holdings and balances
- **Orders**: Place, query, and cancel orders (market and limit)

### Trading Bot Ready
- Clean API for integration with ML models
- Helper methods for common operations
- Proper error handling
- Type hints throughout

## API Documentation

Official Robinhood Crypto API docs:
https://docs.robinhood.com/crypto/trading/

## Examples

See the `py/robinhood_trading/examples/` directory:
- **basic_usage.py** - Account info, prices, holdings
- **order_management.py** - Placing and managing orders
- **trading_bot_integration.py** - Simple bot with moving averages

## Rate Limits

- 100 requests per minute per account
- 300 requests per minute in bursts

## Security Best Practices

1. Never commit encrypted key files to git
2. Keep private keys secret
3. Use strong passwords for password-based encryption
4. Backup encrypted keys securely
5. Rotate keys regularly

## Comparison: New vs Legacy

| Feature | New (`robinhood_trading`) | Legacy |
|---------|---------------------------|--------|
| Credential Storage | Encrypted (AES-256) | Plain JSON file |
| API Interface | Clean methods | Manual request building |
| Type Safety | Full type hints | No types |
| Documentation | Comprehensive | Limited |
| Bot Integration | Easy integration | Coupled implementation |
| Security | Industry standard | Basic |

## Future Plans

- [ ] Websocket support for real-time data
- [ ] Advanced order types (stop-loss, stop-limit)
- [ ] Portfolio analytics
- [ ] Transaction history export
- [ ] Paper trading mode
- [ ] Unified interface for multiple exchanges

## Contributing

Contributions welcome! Areas for improvement:
- Additional helper methods
- More examples
- Better error messages
- Testing suite

## Disclaimer

**This software is for educational purposes only. Cryptocurrency trading carries significant risk.**

- Test thoroughly before live trading
- Understand the risks involved
- Never trade more than you can afford to lose
- This is not financial advice
- Past performance does not guarantee future results

## License

See individual package licenses.

## Support

- **robinhood_trading**: See package README
- **Robinhood API**: https://docs.robinhood.com
- **Trading strategies**: Educational purposes only
