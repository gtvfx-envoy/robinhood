"""https://docs.robinhood.com/crypto/trading/#section/Getting-Started"""

import base64
import datetime
import json
import os
import uuid
from typing import Any, Dict, Optional

import requests
from nacl.signing import SigningKey
from urllib.parse import quote, urljoin

from ._decorators import logFunc


def _get_keys(service_key_file: str = "//THO_CLOUD/gavyn/service/robinhood.json") -> Dict[str, str]:
    """Load API keys from ``service_key_file`` if it exists.

    The original implementation attempted to read the service key file at import
    time which caused ``FileNotFoundError`` during test collection.  The function
    now returns an empty dictionary when the file is missing so that ``ApiClient``
    can still be instantiated in tests without real credentials.
    """

    try:
        with open(service_key_file, "r") as key_file:
            return json.load(key_file)
    except FileNotFoundError:
        # In test environments the service file will not be present.
        return {}




class ApiClient:
    """A client for interacting with the Robinhood Crypto Trading API.

    This class handles authentication, making API requests, and provides methods
    for various trading operations such as placing orders, retrieving account information,
    and fetching trading pairs and holdings.

    Attributes:
        api_key (str): The API key for authentication.
        private_key (SigningKey): The private key used for signing requests.
        base_url (str): The base URL for the Robinhood Crypto Trading API.

    """
    def __init__(self, key_file: str | None = None):
        """Create the API client.

        ``key_file`` allows tests to pass in a dummy location.  When the file is
        missing, the client will simply operate without credentials which is
        sufficient for the unit tests where all network interaction is mocked.
        """

        keys = _get_keys(key_file or "//THO_CLOUD/gavyn/service/robinhood.json")
        self.api_key = keys.get("api", "")
        private_b64 = keys.get("private", "")
        if private_b64:
            try:
                private_key_seed = base64.b64decode(private_b64)
                self.private_key = SigningKey(private_key_seed)
            except Exception:
                self.private_key = None
        else:
            self.private_key = None

        self.base_url = "https://trading.robinhood.com"

    @staticmethod
    def _get_current_timestamp() -> int:
        return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

    @staticmethod
    def get_query_params(key: str, *args: Optional[str]) -> str:
        if not args:
            return ""

        params = []
        for arg in args:
            params.append(f"{key}={arg}")

        return "?" + "&".join(params)

    @logFunc(force=True)
    def make_api_request(self, method: str, path: str, body: str="") -> Any:
        timestamp = self._get_current_timestamp()
        headers = self.get_authorization_header(method, path, body, timestamp)
        url = quote(urljoin(self.base_url, path), safe="/:?=&")

        print(f"url: {url}")
        print(f"headers: {headers}")

        try:
            response = {}
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                body = body or "{}" # Ensure a JSON serializable object is passed
                response = requests.post(url, headers=headers, json=json.loads(body), timeout=10)

            if response:
                return response.json() or {}
            else:
                raise requests.RequestException(response.reason)
        except requests.RequestException as e:
            print(f"Error making API request: {e}")
            return None

    @logFunc(force=True)
    def get_authorization_header(
            self, method: str, path: str, body: str, timestamp: int
    ) -> Dict[str, str]:
        
        message_to_sign = f"{self.api_key}{timestamp}{path}{method}{body}"

        print("DEBUGGING SIGNATURE ISSUE:")
        print(f"API Key: {self.api_key}")
        print(f"Timestamp: {timestamp}")
        print(f"Path: {path}")
        print(f"Method: {method}")
        print(f"Body: {body}")
        print(f"Message to Sign: {message_to_sign}")

        try:
            signed = self.private_key.sign(message_to_sign.encode("utf-8"))
            signature_b64 = base64.b64encode(signed.signature).decode("utf-8")

            print(f"Raw Signature (Hex): {signed.signature.hex()}")
            print(f"Base64 Signature: {signature_b64}")

            return {
                "x-api-key": self.api_key,
                "x-signature": signature_b64,
                "x-timestamp": str(timestamp),
            }
        except Exception as e:
            print(f"Error signing message: {e}")
            return {}

    def get_account(self) -> Any:
        path = "/api/v1/crypto/trading/accounts/"
        return self.make_api_request("GET", path)

    # The symbols argument must be formatted in trading pairs, e.g "BTC-USD", "ETH-USD". If no symbols are provided,
    # all supported symbols will be returned
    def get_trading_pairs(self, *symbols: Optional[str]) -> Any:
        query_params = self.get_query_params("symbol", *symbols)
        path = f"/api/v1/crypto/trading/trading_pairs/{query_params}"
        return self.make_api_request("GET", path)

    # The asset_codes argument must be formatted as the short form name for a crypto, e.g "BTC", "ETH". If no asset
    # codes are provided, all crypto holdings will be returned
    def get_holdings(self, *asset_codes: Optional[str]) -> Any:
        query_params = self.get_query_params("asset_code", *asset_codes)
        path = f"/api/v1/crypto/trading/holdings/{query_params}"
        return self.make_api_request("GET", path)

    # The symbols argument must be formatted in trading pairs, e.g "BTC-USD", "ETH-USD". If no symbols are provided,
    # the best bid and ask for all supported symbols will be returned
    def get_best_bid_ask(self, *symbols: Optional[str]) -> Any:
        query_params = self.get_query_params("symbol", *symbols)
        path = f"/api/v1/crypto/marketdata/best_bid_ask/{query_params}"
        return self.make_api_request("GET", path)

    # The symbol argument must be formatted in a trading pair, e.g "BTC-USD", "ETH-USD"
    # The side argument must be "bid", "ask", or "both".
    # Multiple quantities can be specified in the quantity argument, e.g. "0.1,1,1.999".
    def get_estimated_price(self, symbol: str, side: str, quantity: str) -> Any:
        path = f"/api/v1/crypto/marketdata/estimated_price/?symbol={symbol}&side={side}&quantity={quantity}"
        return self.make_api_request("GET", path)

    @logFunc(force=True)
    def _place_order(
            self,
            client_order_id: str,
            side: str,
            order_type: str,
            symbol: str,
            order_config: Dict[str, str],
    ) -> Any:
        body = {
            "client_order_id": client_order_id,
            "side": side,
            "type": order_type,
            "symbol": symbol,
            f"{order_type}_order_config": order_config,
        }

        path = "/api/v1/crypto/trading/orders/"
        return self.make_api_request("POST", path, json.dumps(body))
    
    @logFunc(force=True)
    def place_order(self, side: str, order_type: str, symbol: str,
                    order_config: Dict[str, str]) -> Any:
        body = {
            "client_order_id": str(uuid.uuid4()),
            "side": side,
            "type": order_type,
            "symbol": symbol,
            f"{order_type}_order_config": order_config,
        }

        path = "/api/v1/crypto/trading/orders/"
        return self.make_api_request("POST", path, json.dumps(body, separators=(',', ':')))
    
    @logFunc(force=True)
    def place_limit_order(self, side, symbol, quantity,
                        limit_price, time_in_force):
        """
        
        
        """
        order_config = {
            "asset_quantity": quantity,
            "limit_price": limit_price,
            "time_in_force": time_in_force.lower()
        }

        return self.place_order(side,
                                "limit",
                                symbol,
                                order_config)
    
    @logFunc(force=True)
    def place_limit_buy(self, symbol, quantity, limit_price,
                         time_in_force):
        """
        
        
        """
        return self.place_limit_order("buy",
                                      symbol,
                                      quantity,
                                      limit_price,
                                      time_in_force)
    
    @logFunc(force=True)
    def place_limit_sell(self, symbol, quantity, limit_price,
                         time_in_force):
        """
        
        
        """
        return self.place_limit_order("sell",
                                      symbol,
                                      quantity,
                                      limit_price,
                                      time_in_force)
    
    @logFunc(force=True)
    def place_market_order(self, side, symbol, quantity):
        """
        
        
        """
        order_config = {
            "asset_quantity": str(quantity)
        }

        return self.place_order(side,
                                "market",
                                symbol,
                                order_config)
    
    @logFunc(force=True)
    def place_market_buy(self, symbol, quantity):
        """
        
        
        """
        return self.place_market_order("buy",
                                       symbol,
                                       quantity)


    @logFunc(force=True)
    def place_market_sell(self, symbol, quantity):
        """
        
        
        """
        return self.place_market_order("sell",
                                       symbol,
                                       quantity)

    def cancel_order(self, order_id: str) -> Any:
        """
        
        """
        path = f"/api/v1/crypto/trading/orders/{order_id}/cancel/"
        return self.make_api_request("POST", path)

    def get_order(self, order_id: str) -> Any:
        """
        
        """
        path = f"/api/v1/crypto/trading/orders/{order_id}/"
        return self.make_api_request("GET", path)

    def get_orders(self) -> Any:
        """
        
        """
        path = "/api/v1/crypto/trading/orders/"
        return self.make_api_request("GET", path)


def main():
    api_trading_client = CryptoAPITrading()
    print(api_trading_client.get_account())

    """
    BUILD YOUR TRADING STRATEGY HERE

    order = api_trading_client.place_order(
          str(uuid.uuid4()),
          "buy",
          "market",
          "BTC-USD",
          {"asset_quantity": "0.00001"}
    )
    """


if __name__ == "__main__":
    main()
