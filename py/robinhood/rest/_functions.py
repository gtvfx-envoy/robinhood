"""Convenience functions for interacting with API


Examples:
https://docs.robinhood.com/crypto/trading/#tag/Trading/operation/api_v1_crypto_trading_orders

### Order config examples
`Payload`
{
  "symbol": "string",
  "client_order_id": "11299b2b-61e3-43e7-b9f7-dee77210bb29",
  "side": "buy",
  "type": "limit",
  "market_order_config": {
    "asset_quantity": 0
  },
  "limit_order_config": {
    "quote_amount": 0,
    "asset_quantity": 0,
    "limit_price": 0,
    "time_in_force": "gtc"
  },
  "stop_loss_order_config": {
    "quote_amount": 0,
    "asset_quantity": 0,
    "stop_price": 0,
    "time_in_force": "gtc"
  },
  "stop_limit_order_config": {
    "quote_amount": 0,
    "asset_quantity": 0,
    "limit_price": 0,
    "stop_price": 0,
    "time_in_force": "gtc"
  }
}


"""
import json
from typing import Any, Dict, Optional
import uuid

from ._decorators import logFunc
from ._enums import OrderSides, EstimateSides, OrderState, OrderType, TimeInForce
from ._interface import Robinhood as rh


__all__ = [
    "get_query_params",
    "get_account",
    "get_trading_pairs",
    "get_holdings",
    "get_best_bid_ask",
    "get_estimated_price",
    "place_order",
    "place_market_order",
    "place_market_buy",
    "place_market_sell",
    "place_limit_order",
    "place_limit_buy",
    "place_limit_sell",
    "cancel_order",
    "get_order",
    "get_orders"
]


@logFunc(force=True)
def get_query_params(key: str, *args: Optional[str]) -> str:
    if not args:
        return ""

    params = []
    for arg in args:
        params.append(f"{key}={arg}")

    return "?" + "&".join(params)

@logFunc(force=True)
def get_account() -> Any:
    """
    
    Args:

    
    Returns:
        JSON
    
    """
    path = "/api/v1/crypto/trading/accounts/"
    return rh().get(path)


# The symbols argument must be formatted in trading pairs, e.g "BTC-USD", "ETH-USD". If no symbols are provided,
# all supported symbols will be returned
@logFunc(force=True)
def get_trading_pairs(*symbols: Optional[str]) -> Any:
    """
    
    Args:

    
    Returns:
        JSON
    
    """
    query_params = get_query_params("symbol", *symbols)
    path = f"/api/v1/crypto/trading/trading_pairs/{query_params}"
    return rh().get(path)


# The asset_codes argument must be formatted as the short form name for a crypto, e.g "BTC", "ETH". If no asset
# codes are provided, all crypto holdings will be returned
@logFunc(force=True)
def get_holdings(*asset_codes: Optional[str]) -> Any:
    """
    
    Args:

    
    Returns:
        JSON
    
    """
    query_params = get_query_params("asset_code", *asset_codes)
    path = f"/api/v1/crypto/trading/holdings/{query_params}"
    return rh().get(path)


# The symbols argument must be formatted in trading pairs, e.g "BTC-USD", "ETH-USD". If no symbols are provided,
# the best bid and ask for all supported symbols will be returned
@logFunc(force=True)
def get_best_bid_ask(*symbols: Optional[str]) -> Any:
    """
    
    Args:

    
    Returns:
        JSON
    
    """
    query_params = get_query_params("symbol", *symbols)
    path = f"/api/v1/crypto/marketdata/best_bid_ask/{query_params}"
    return rh().get(path)


# The symbol argument must be formatted in a trading pair, e.g "BTC-USD", "ETH-USD"
# The side argument must be "bid", "ask", or "both".
# Multiple quantities can be specified in the quantity argument, e.g. "0.1,1,1.999".
@logFunc(force=True)
def get_estimated_price(symbol: str, side: str, quantity: str) -> Any:
    """
    
    Args:

    
    Returns:
        JSON
    
    """
    assert side.lower() in EstimateSides._value2member_map_, f"side must be one of {[v.value for v in EstimateSides]}"

    path = f"/api/v1/crypto/marketdata/estimated_price/?symbol={symbol}&side={side}&quantity={quantity}"
    return rh().get(path)


@logFunc(force=True)
def place_order(side: str,
                order_type: str,
                symbol: str,
                order_config: Dict[str, str],
                client_order_id: str="") -> Any:
    """
    
    Args:

    
    Returns:
        JSON
    
    """
    assert side.lower() in OrderSides._value2member_map_, f"side must be one of {[v.value for v in OrderSides]}"
    assert order_type.lower() in OrderType._value2member_map_, f"side must be one of {[v.value for v in OrderType]}"


    body = {
        "client_order_id": client_order_id or str(uuid.uuid4()),
        "side": side,
        "type": order_type,
        "symbol": symbol,
        f"{order_type}_order_config": order_config,
    }

    path = "/api/v1/crypto/trading/orders/"
    return rh().post(path, body=json.dumps(body)) # Ensure compact JSON format


@logFunc(force=True)
def place_market_order(side, symbol, quantity, client_order_id=""):
    """
    
    
    """
    order_config = {
        "asset_quantity": str(quantity)
    }

    return place_order(side,
                       OrderType.MARKET.value,
                       symbol,
                       order_config,
                       client_order_id=client_order_id)


@logFunc(force=True)
def place_market_buy(symbol, quantity, client_order_id=""):
    """
    
    
    """
    return place_market_order(OrderSides.BUY.value,
                              symbol,
                              quantity,
                              client_order_id=client_order_id)


@logFunc(force=True)
def place_market_sell(symbol, quantity, client_order_id=""):
    """
    
    
    """
    return place_market_order(OrderSides.SELL.value,
                              symbol,
                              quantity,
                              client_order_id=client_order_id)


@logFunc(force=True)
def place_limit_order(side, symbol, quantity,
                      limit_price, time_in_force, client_order_id=""):
    """
    
    
    """
    assert time_in_force.lower() in TimeInForce._value2member_map_, f"side must be one of {[v.value for v in TimeInForce]}"
    
    order_config = {
        "asset_quantity": quantity,
        "limit_price": limit_price,
        "time_in_force": time_in_force.lower()
    }

    return place_order(side,
                       OrderType.LIMIT.value,
                       symbol,
                       order_config,
                       client_order_id=client_order_id)


@logFunc(force=True)
def place_limit_buy(symbol, quantity, limit_price,
                    time_in_force, client_order_id=""):
    """
    
    
    """
    return place_limit_order(OrderSides.BUY.value,
                             symbol,
                             quantity,
                             limit_price,
                             time_in_force,
                             client_order_id=client_order_id)


@logFunc(force=True)
def place_limit_sell(symbol, quantity, limit_price,
                     time_in_force, client_order_id=""):
    """
    
    
    """
    return place_limit_order(OrderSides.SELL.value,
                             symbol,
                             quantity,
                             limit_price,
                             time_in_force,
                             client_order_id=client_order_id)


@logFunc(force=True)
def cancel_order(order_id: str) -> Dict[str, Any]:
    """
    
    
    """
    path = f"/api/v1/crypto/trading/orders/{order_id}/cancel/"
    return rh().post(path)


@logFunc(force=True)
def get_order(order_id: str) -> Dict[str, Any]:
    """
    
    
    """
    path = f"/api/v1/crypto/trading/orders/{order_id}/"
    return rh().get(path)
    

@logFunc(force=True)
def get_orders() -> Dict[str, Any]:
    """
    
    
    """
    path = "/api/v1/crypto/trading/orders/"
    return rh().get(path)
