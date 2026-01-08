"""
Robinhood Crypto Trading API - Python Interface

A clean, secure Python interface for the Robinhood Crypto Trading API
with optional encrypted credential storage and full endpoint coverage.

Modules:
    key_manager: Secure storage and retrieval of API keys (optional)
    client: Robinhood API client with all trading endpoints
    adapter: Trading bot exchange adapter

Classes:
    RobinhoodClient: Main API client for Robinhood Crypto trading
    RobinhoodExchangeAdapter: Adapter for trading_bot framework
    KeyManager: Optional encrypted API key storage

Quick Start:
    # Option 1: Direct initialization (simplest)
    from robinhood.trading import RobinhoodClient
    import os
    
    api_key = os.getenv("ROBINHOOD_API_KEY")
    private_key = os.getenv("ROBINHOOD_PRIVATE_KEY")
    client = RobinhoodClient(api_key, private_key)
    
    # Get account details
    account = client.get_account()
    
    # Get current price
    price = client.get_current_price("BTC-USD")
    
    # Option 2: With KeyManager for encrypted storage
    from robinhood.trading import RobinhoodClient, KeyManager
    
    manager = KeyManager()
    client = RobinhoodClient.from_key_manager(manager, password="your_password")
"""

from .key_manager import KeyManager, setup_encrypted_storage
from .client import RobinhoodClient
from .adapter import RobinhoodExchangeAdapter
from .setup_keys import setup_keys, get_keys

__all__ = [
    'KeyManager',
    'RobinhoodClient',
    'RobinhoodExchangeAdapter',
    'setup_encrypted_storage',
    'setup_keys',
    'get_keys'
]

__version__ = '1.0.0'
