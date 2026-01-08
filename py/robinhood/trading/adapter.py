"""Robinhood Exchange Adapter for trading_bot.

This module provides an adapter that implements the trading_bot ExchangeClient
interface, allowing the trading bot to work with Robinhood's API.

"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
from trading_bot.exchange_client import ExchangeClient
from .client import RobinhoodClient


class RobinhoodExchangeAdapter(ExchangeClient):
    """Robinhood adapter implementing the trading_bot ExchangeClient interface.
    
    This adapter wraps the RobinhoodClient to provide the standard
    exchange interface expected by the trading bot.
    
    Example:
        >>> from robinhood.trading import RobinhoodClient, KeyManager
        >>> from robinhood.trading.adapter import RobinhoodExchangeAdapter
        >>> 
        >>> # Setup client
        >>> manager = KeyManager()
        >>> client = RobinhoodClient.from_key_manager(manager, password="your_password")
        >>> 
        >>> # Create adapter
        >>> adapter = RobinhoodExchangeAdapter(client)
        >>> 
        >>> # Use with trading bot
        >>> from trading_bot import TradingBot, TradingConfig
        >>> config = TradingConfig(trading_pairs=["BTC-USD", "ETH-USD"])
        >>> bot = TradingBot(config, adapter)
    
    """
    
    def __init__(self, client: RobinhoodClient):
        """Initialize adapter with Robinhood client.
        
        Args:
            client: Configured RobinhoodClient instance
        
        """
        self.client = client
        self._cached_account_info = None
        self._cache_timestamp = None
        self._cache_ttl = 5  # seconds
    
    def _refresh_account_cache(self, force: bool = False):
        """Refresh cached account information.
        
        Args:
            force: Force refresh even if cache is valid
        
        """
        now = datetime.now().timestamp()
        
        if force or self._cached_account_info is None or \
           (self._cache_timestamp and now - self._cache_timestamp > self._cache_ttl):
            self._cached_account_info = self.client.get_account()
            self._cache_timestamp = now
    
    def get_account_balance(self) -> Dict[str, float]:
        """Get account balances for all assets.
        
        Returns:
            Dictionary mapping asset code to available balance
            Example: {'USD': 10000.0, 'BTC': 0.5, 'ETH': 2.0}
        
        """
        holdings_response = self.client.get_holdings()
        balances = {}
        
        # Add USD buying power
        self._refresh_account_cache()
        if self._cached_account_info and 'results' in self._cached_account_info:
            account = self._cached_account_info['results'][0]
            balances['USD'] = float(account.get('buying_power', 0))
        
        # Add crypto holdings
        if 'results' in holdings_response:
            for holding in holdings_response['results']:
                asset_code = holding.get('asset_code')
                total_quantity = float(holding.get('total_quantity', 0))
                if total_quantity > 0:
                    balances[asset_code] = total_quantity
        
        return balances
    
    def get_buying_power(self) -> float:
        """Get available buying power in USD.
        
        Returns:
            Available USD balance for trading
        
        """
        self._refresh_account_cache()
        
        if self._cached_account_info and 'results' in self._cached_account_info:
            account = self._cached_account_info['results'][0]
            return float(account.get('buying_power', 0))
        
        return 0.0
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a trading pair.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            
        Returns:
            Current price or None if unavailable
        
        """
        return self.client.get_current_price(symbol)
    
    def get_historical_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        granularity: str
    ) -> pd.DataFrame:
        """Get historical OHLCV candlestick data.
        
        Note: Robinhood's API doesn't directly provide historical candlestick data.
        This is a placeholder implementation that returns an empty DataFrame.
        For production use, you would need to integrate with a market data provider
        or implement a custom solution.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            start: Start datetime
            end: End datetime
            granularity: Time interval (e.g., "1h", "1d")
            
        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
        
        """
        # TODO: Implement historical data fetching
        # This could use a third-party data provider since Robinhood doesn't
        # provide historical candles in their crypto API
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float
    ) -> Dict[str, Any]:
        """Place a market order.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            side: "buy" or "sell"
            quantity: Amount of asset to trade
            
        Returns:
            Order details dictionary with at least {'id', 'status', 'filled_quantity'}
        
        """
        response = self.client.place_market_order(
            symbol=symbol,
            side=side,
            quantity=quantity
        )
        
        # Normalize response to standard format
        return {
            'id': response.get('id'),
            'status': response.get('state'),
            'symbol': response.get('symbol'),
            'side': response.get('side'),
            'type': 'market',
            'quantity': float(response.get('quantity', 0)),
            'filled_quantity': float(response.get('executed_quantity', 0)),
            'average_price': float(response.get('average_price', 0)) if response.get('average_price') else None,
            'created_at': response.get('created_at'),
            'raw_response': response
        }
    
    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ) -> Dict[str, Any]:
        """Place a limit order.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            side: "buy" or "sell"
            quantity: Amount of asset to trade
            price: Limit price
            
        Returns:
            Order details dictionary with at least {'id', 'status'}
        
        """
        response = self.client.place_limit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price
        )
        
        # Normalize response to standard format
        return {
            'id': response.get('id'),
            'status': response.get('state'),
            'symbol': response.get('symbol'),
            'side': response.get('side'),
            'type': 'limit',
            'quantity': float(response.get('quantity', 0)),
            'price': float(response.get('price', 0)),
            'filled_quantity': float(response.get('executed_quantity', 0)),
            'average_price': float(response.get('average_price', 0)) if response.get('average_price') else None,
            'created_at': response.get('created_at'),
            'raw_response': response
        }
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if successfully cancelled, False otherwise
        
        """
        try:
            response = self.client.cancel_order(order_id)
            # Check if cancellation was successful
            state = response.get('state', '').lower()
            return state in ['canceled', 'cancelled']
        except Exception:
            return False
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status and details.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order details dictionary with at least {'id', 'status', 'filled_quantity'}
        
        """
        response = self.client.get_order(order_id)
        
        # Normalize response to standard format
        return {
            'id': response.get('id'),
            'status': response.get('state'),
            'symbol': response.get('symbol'),
            'side': response.get('side'),
            'type': response.get('type'),
            'quantity': float(response.get('quantity', 0)),
            'filled_quantity': float(response.get('executed_quantity', 0)),
            'price': float(response.get('price', 0)) if response.get('price') else None,
            'average_price': float(response.get('average_price', 0)) if response.get('average_price') else None,
            'created_at': response.get('created_at'),
            'updated_at': response.get('updated_at'),
            'raw_response': response
        }
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open orders.
        
        Args:
            symbol: Optional trading pair to filter by
            
        Returns:
            List of order dictionaries
        
        """
        response = self.client.get_orders(
            symbol=symbol,
            state='open'
        )
        
        orders = []
        if 'results' in response:
            for order in response['results']:
                orders.append({
                    'id': order.get('id'),
                    'status': order.get('state'),
                    'symbol': order.get('symbol'),
                    'side': order.get('side'),
                    'type': order.get('type'),
                    'quantity': float(order.get('quantity', 0)),
                    'filled_quantity': float(order.get('executed_quantity', 0)),
                    'price': float(order.get('price', 0)) if order.get('price') else None,
                    'created_at': order.get('created_at'),
                    'raw_response': order
                })
        
        return orders
    
    def get_holdings(self) -> Dict[str, float]:
        """Get current holdings/positions.
        
        Returns:
            Dictionary mapping asset code to total quantity held
        
        """
        holdings_response = self.client.get_holdings()
        holdings = {}
        
        if 'results' in holdings_response:
            for holding in holdings_response['results']:
                asset_code = holding.get('asset_code')
                total_quantity = float(holding.get('total_quantity', 0))
                if total_quantity > 0:
                    holdings[asset_code] = total_quantity
        
        return holdings
    
    def supports_stop_loss(self) -> bool:
        """Check if exchange supports stop-loss orders.
        
        Robinhood crypto API does not currently support stop-loss orders.
        
        Returns:
            False
        
        """
        return False
