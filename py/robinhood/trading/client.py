"""Robinhood Crypto Trading API Client.

This module provides a clean Python interface to the Robinhood Crypto Trading API
with secure credential management and full endpoint coverage.

"""
import base64
import datetime
import json
from typing import Any, Dict, Optional, List
import requests
from nacl.signing import SigningKey

from .key_manager import KeyManager


class RobinhoodClient:
    """Robinhood Crypto Trading API client."""
    
    def __init__(self, api_key: str, private_key_base64: str):
        """Initialize Robinhood client.
        
        Args:
            api_key: Robinhood API key
            private_key_base64: Base64-encoded Ed25519 private key

        """
        self.api_key = api_key
        private_key_seed = base64.b64decode(private_key_base64)
        self.private_key = SigningKey(private_key_seed)
        self.base_url = "https://trading.robinhood.com"
    
    @classmethod
    def from_key_manager(
        cls,
        manager: KeyManager,
        cipher_key: Optional[bytes] = None,
        password: Optional[str] = None
    ) -> 'RobinhoodClient':
        """Create client from KeyManager.
        
        Args:
            manager: KeyManager instance
            cipher_key: Encryption key (for file-based encryption)
            password: Password (for password-based encryption)
            
        Returns:
            RobinhoodClient instance

        """
        if password:
            credentials = manager.load_with_password(password)
        elif cipher_key:
            credentials = manager.load_encrypted_keys(cipher_key)
        else:
            raise ValueError("Must provide either cipher_key or password")
        
        return cls(
            api_key=credentials['api_key'],
            private_key_base64=credentials['private_key']
        )
    
    @staticmethod
    def _get_current_timestamp() -> int:
        """Get current Unix timestamp."""
        return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
    
    def _get_authorization_headers(
        self,
        method: str,
        path: str,
        body: str = ""
    ) -> Dict[str, str]:
        """Generate authorization headers for API request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            body: Request body as JSON string
            
        Returns:
            Dictionary of headers

        """
        timestamp = self._get_current_timestamp()
        
        # Create message to sign
        message_to_sign = f"{self.api_key}{timestamp}{path}{method}{body}"
        
        # Sign message
        signed = self.private_key.sign(message_to_sign.encode("utf-8"))
        signature_b64 = base64.b64encode(signed.signature).decode("utf-8")
        
        return {
            "x-api-key": self.api_key,
            "x-signature": signature_b64,
            "x-timestamp": str(timestamp),
            "Content-Type": "application/json"
        }
    
    def _make_request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make authenticated API request.
        
        Args:
            method: HTTP method
            path: API endpoint path
            body: Request body dictionary
            params: Query parameters
            
        Returns:
            Response data as dictionary

        """
        # Prepare body
        body_str = json.dumps(body) if body else ""
        
        # Build query string for signature if params exist
        path_with_params = path
        if params:
            from urllib.parse import urlencode
            query_string = urlencode(params, doseq=True)
            path_with_params = f"{path}?{query_string}"
        
        # Get headers (must include query string in signature)
        headers = self._get_authorization_headers(method, path_with_params, body_str)
        
        # Build URL
        url = self.base_url + path
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == "POST":
                response = requests.post(
                    url,
                    headers=headers,
                    json=body if body else {},
                    params=params,
                    timeout=10
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check for errors
            response.raise_for_status()
            
            # Return JSON response
            return response.json() if response.text else {}
            
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print(f"Response: {e.response.text if e.response else 'No response'}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}")
            raise
    
    # ==================== Account Methods ====================
    
    def get_account(self) -> Dict[str, Any]:
        """Get Robinhood Crypto trading account details.
        
        Returns:
            Dictionary with account_number, status, buying_power, etc.

        """
        path = "/api/v1/crypto/trading/accounts/"
        return self._make_request("GET", path)
    
    # ==================== Market Data Methods ====================
    
    def get_best_bid_ask(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get best bid and ask prices for symbols.
        
        Args:
            symbols: List of trading pairs (e.g., ["BTC-USD", "ETH-USD"])
                    If None, returns all supported symbols
            
        Returns:
            Dictionary with results list containing bid/ask data

        """
        path = "/api/v1/crypto/marketdata/best_bid_ask/"
        params = {}
        
        if symbols:
            # Multiple symbols: symbol=BTC-USD&symbol=ETH-USD
            params = {'symbol': symbols}
        
        return self._make_request("GET", path, params=params)
    
    def get_estimated_price(
        self,
        symbol: str,
        side: str,
        quantity: str
    ) -> Dict[str, Any]:
        """Get estimated price for a trade.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            side: "bid", "ask", or "both"
            quantity: Comma-separated quantities (e.g., "0.1,1,1.999")
            
        Returns:
            Dictionary with estimated prices

        """
        path = "/api/v1/crypto/marketdata/estimated_price/"
        params = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity
        }
        return self._make_request("GET", path, params=params)
    
    # ==================== Trading Pairs Methods ====================
    
    def get_trading_pairs(
        self,
        symbols: Optional[List[str]] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get available trading pairs.
        
        Args:
            symbols: List of trading pairs to filter by
            limit: Limit number of results per page
            cursor: Pagination cursor
            
        Returns:
            Dictionary with results, next, and previous fields

        """
        path = "/api/v1/crypto/trading/trading_pairs/"
        params = {}
        
        if symbols:
            params['symbol'] = symbols
        if limit:
            params['limit'] = limit
        if cursor:
            params['cursor'] = cursor
        
        return self._make_request("GET", path, params=params)
    
    # ==================== Holdings Methods ====================
    
    def get_holdings(
        self,
        asset_codes: Optional[List[str]] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get crypto holdings.
        
        Args:
            asset_codes: List of asset codes (e.g., ["BTC", "ETH"])
            limit: Limit number of results per page
            cursor: Pagination cursor
            
        Returns:
            Dictionary with holdings results

        """
        path = "/api/v1/crypto/trading/holdings/"
        params = {}
        
        if asset_codes:
            params['asset_code'] = asset_codes
        if limit:
            params['limit'] = limit
        if cursor:
            params['cursor'] = cursor
        
        return self._make_request("GET", path, params=params)
    
    # ==================== Order Methods ====================
    
    def get_orders(
        self,
        symbol: Optional[str] = None,
        order_id: Optional[str] = None,
        side: Optional[str] = None,
        state: Optional[str] = None,
        order_type: Optional[str] = None,
        created_at_start: Optional[str] = None,
        created_at_end: Optional[str] = None,
        updated_at_start: Optional[str] = None,
        updated_at_end: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get list of orders with optional filters.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            order_id: Specific order ID
            side: "buy" or "sell"
            state: "open", "canceled", "partially_filled", "filled", or "failed"
            order_type: "limit", "market", "stop_limit", or "stop_loss"
            created_at_start: ISO 8601 timestamp
            created_at_end: ISO 8601 timestamp
            updated_at_start: ISO 8601 timestamp
            updated_at_end: ISO 8601 timestamp
            limit: Limit number of results
            cursor: Pagination cursor
            
        Returns:
            Dictionary with orders results

        """
        path = "/api/v1/crypto/trading/orders/"
        params = {}
        
        if symbol:
            params['symbol'] = symbol
        if order_id:
            params['id'] = order_id
        if side:
            params['side'] = side
        if state:
            params['state'] = state
        if order_type:
            params['type'] = order_type
        if created_at_start:
            params['created_at_start'] = created_at_start
        if created_at_end:
            params['created_at_end'] = created_at_end
        if updated_at_start:
            params['updated_at_start'] = updated_at_start
        if updated_at_end:
            params['updated_at_end'] = updated_at_end
        if limit:
            params['limit'] = limit
        if cursor:
            params['cursor'] = cursor
        
        return self._make_request("GET", path, params=params)
    
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get specific order details.
        
        Args:
            order_id: Order ID
            
        Returns:
            Dictionary with order details

        """
        path = f"/api/v1/crypto/trading/orders/{order_id}/"
        return self._make_request("GET", path)
    
    def place_market_order(
        self,
        symbol: str,
        side: str,
        asset_quantity: float,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Place a market order.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            side: "buy" or "sell"
            asset_quantity: Amount of asset to trade
            client_order_id: Custom order ID (generated if not provided)
            
        Returns:
            Dictionary with order details

        """
        import uuid
        
        if client_order_id is None:
            client_order_id = str(uuid.uuid4())
        
        body = {
            "client_order_id": client_order_id,
            "side": side,
            "type": "market",
            "symbol": symbol,
            "market_order_config": {
                "asset_quantity": str(asset_quantity)
            }
        }
        
        path = "/api/v1/crypto/trading/orders/"
        return self._make_request("POST", path, body=body)
    
    def place_limit_order(
        self,
        symbol: str,
        side: str,
        limit_price: float,
        asset_quantity: Optional[float] = None,
        quote_amount: Optional[float] = None,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Place a limit order.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            side: "buy" or "sell"
            limit_price: Limit price
            asset_quantity: Amount of asset (either this or quote_amount)
            quote_amount: Amount in quote currency (either this or asset_quantity)
            client_order_id: Custom order ID (generated if not provided)
            
        Returns:
            Dictionary with order details

        """
        import uuid
        
        if client_order_id is None:
            client_order_id = str(uuid.uuid4())
        
        if asset_quantity is None and quote_amount is None:
            raise ValueError("Must provide either asset_quantity or quote_amount")
        
        if asset_quantity is not None and quote_amount is not None:
            raise ValueError("Cannot provide both asset_quantity and quote_amount")
        
        limit_config = {"limit_price": str(limit_price)}
        
        if asset_quantity is not None:
            limit_config["asset_quantity"] = str(asset_quantity)
        else:
            limit_config["quote_amount"] = str(quote_amount)
        
        body = {
            "client_order_id": client_order_id,
            "side": side,
            "type": "limit",
            "symbol": symbol,
            "limit_order_config": limit_config
        }
        
        path = "/api/v1/crypto/trading/orders/"
        return self._make_request("POST", path, body=body)
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Cancellation confirmation

        """
        path = f"/api/v1/crypto/trading/orders/{order_id}/cancel/"
        return self._make_request("POST", path)
    
    # ==================== Helper Methods ====================
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            
        Returns:
            Current price as float or None if error

        """
        try:
            response = self.get_best_bid_ask([symbol])
            if response and 'results' in response and response['results']:
                result = response['results'][0]
                # Use the price field directly, or calculate mid from bid/ask
                if 'price' in result:
                    return float(result['price'])
                # Fallback: calculate mid price from bid and ask
                bid = float(result.get('bid_inclusive_of_sell_spread', 0))
                ask = float(result.get('ask_inclusive_of_buy_spread', 0))
                return (bid + ask) / 2 if bid and ask else None
            return None
        except Exception as e:
            print(f"Error getting price for {symbol}: {e}")
            return None
    
    def get_balance(self, asset_code: str) -> Optional[float]:
        """Get balance for a specific asset.
        
        Args:
            asset_code: Asset code (e.g., "BTC", "USD")
            
        Returns:
            Available balance as float or None if not found

        """
        try:
            response = self.get_holdings([asset_code])
            if response and 'results' in response:
                for holding in response['results']:
                    if holding.get('asset_code') == asset_code:
                        return float(holding.get('total_quantity', 0))
            return None
        except Exception as e:
            print(f"Error getting balance for {asset_code}: {e}")
            return None
