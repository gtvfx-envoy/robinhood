"""
Robinhood Crypto Trading API - Python Interface

A clean, secure Python interface for the Robinhood Crypto Trading API
with encrypted credential storage and full endpoint coverage.

Modules:
    key_manager: Secure storage and retrieval of API keys
    client: Robinhood API client with all trading endpoints

Classes:
    KeyManager: Handles encrypted API key storage
    RobinhoodClient: Main API client for Robinhood Crypto trading

Example:
    from robinhood_trading import RobinhoodClient, KeyManager
    
    # Initialize client
    manager = KeyManager()
    cipher_key = manager.load_cipher_key()
    client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)
    
    # Get account details
    account = client.get_account()
    print(f"Buying power: {account['buying_power']}")
    
    # Get current price
    price = client.get_current_price("BTC-USD")
    print(f"BTC price: ${price}")
"""

from .key_manager import KeyManager, setup_encrypted_storage
from .client import RobinhoodClient

__all__ = [
    'KeyManager',
    'RobinhoodClient',
    'setup_encrypted_storage'
]

__version__ = '1.0.0'
