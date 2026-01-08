"""Tests for Robinhood Exchange Adapter.

Tests that the adapter correctly implements the trading_bot ExchangeClient interface.
"""

import pytest
from unittest.mock import Mock, MagicMock
from robinhood.trading.adapter import RobinhoodExchangeAdapter
from trading_bot.exchange_client import ExchangeClient


def test_adapter_implements_exchange_client():
    """Verify adapter implements the ExchangeClient interface."""
    # Check that adapter is a subclass
    assert issubclass(RobinhoodExchangeAdapter, ExchangeClient)
    
    # Create mock client
    mock_client = Mock()
    adapter = RobinhoodExchangeAdapter(mock_client)
    
    # Verify it's an instance
    assert isinstance(adapter, ExchangeClient)


def test_adapter_has_required_methods():
    """Verify all required methods are implemented."""
    required_methods = [
        'get_account_balance',
        'get_buying_power',
        'get_current_price',
        'get_historical_candles',
        'place_market_order',
        'place_limit_order',
        'cancel_order',
        'get_order_status',
        'get_open_orders',
        'get_holdings',
    ]
    
    mock_client = Mock()
    adapter = RobinhoodExchangeAdapter(mock_client)
    
    for method_name in required_methods:
        assert hasattr(adapter, method_name), f"Missing method: {method_name}"
        method = getattr(adapter, method_name)
        assert callable(method), f"Method not callable: {method_name}"


def test_get_buying_power():
    """Test get_buying_power method."""
    mock_client = Mock()
    mock_client.get_account.return_value = {
        'results': [{
            'buying_power': '10000.50'
        }]
    }
    
    adapter = RobinhoodExchangeAdapter(mock_client)
    buying_power = adapter.get_buying_power()
    
    assert buying_power == 10000.50
    mock_client.get_account.assert_called_once()


def test_get_current_price():
    """Test get_current_price delegates to client."""
    mock_client = Mock()
    mock_client.get_current_price.return_value = 50000.0
    
    adapter = RobinhoodExchangeAdapter(mock_client)
    price = adapter.get_current_price("BTC-USD")
    
    assert price == 50000.0
    mock_client.get_current_price.assert_called_once_with("BTC-USD")


def test_get_holdings():
    """Test get_holdings returns correct format."""
    mock_client = Mock()
    mock_client.get_holdings.return_value = {
        'results': [
            {'asset_code': 'BTC', 'total_quantity': '0.5'},
            {'asset_code': 'ETH', 'total_quantity': '2.0'},
            {'asset_code': 'DOGE', 'total_quantity': '0'},  # Should be filtered out
        ]
    }
    
    adapter = RobinhoodExchangeAdapter(mock_client)
    holdings = adapter.get_holdings()
    
    assert holdings == {'BTC': 0.5, 'ETH': 2.0}
    assert 'DOGE' not in holdings  # Zero holdings excluded


def test_place_market_order():
    """Test place_market_order normalizes response."""
    mock_client = Mock()
    mock_client.place_market_order.return_value = {
        'id': 'order-123',
        'state': 'filled',
        'symbol': 'BTC-USD',
        'side': 'buy',
        'quantity': '0.001',
        'executed_quantity': '0.001',
        'average_price': '50000.0',
        'created_at': '2026-01-01T00:00:00Z'
    }
    
    adapter = RobinhoodExchangeAdapter(mock_client)
    order = adapter.place_market_order("BTC-USD", "buy", 0.001)
    
    # Verify normalized format
    assert order['id'] == 'order-123'
    assert order['status'] == 'filled'
    assert order['type'] == 'market'
    assert order['quantity'] == 0.001
    assert order['filled_quantity'] == 0.001
    assert order['average_price'] == 50000.0
    
    mock_client.place_market_order.assert_called_once_with(
        symbol="BTC-USD",
        side="buy",
        quantity=0.001
    )


def test_cancel_order_success():
    """Test successful order cancellation."""
    mock_client = Mock()
    mock_client.cancel_order.return_value = {
        'id': 'order-123',
        'state': 'canceled'
    }
    
    adapter = RobinhoodExchangeAdapter(mock_client)
    result = adapter.cancel_order('order-123')
    
    assert result is True
    mock_client.cancel_order.assert_called_once_with('order-123')


def test_cancel_order_failure():
    """Test failed order cancellation."""
    mock_client = Mock()
    mock_client.cancel_order.side_effect = Exception("Order not found")
    
    adapter = RobinhoodExchangeAdapter(mock_client)
    result = adapter.cancel_order('order-999')
    
    assert result is False


def test_get_open_orders():
    """Test get_open_orders filters and normalizes."""
    mock_client = Mock()
    mock_client.get_orders.return_value = {
        'results': [
            {
                'id': 'order-1',
                'state': 'open',
                'symbol': 'BTC-USD',
                'side': 'buy',
                'type': 'limit',
                'quantity': '0.001',
                'executed_quantity': '0',
                'price': '45000.0',
                'created_at': '2026-01-01T00:00:00Z'
            },
            {
                'id': 'order-2',
                'state': 'open',
                'symbol': 'ETH-USD',
                'side': 'sell',
                'type': 'limit',
                'quantity': '0.1',
                'executed_quantity': '0',
                'price': '3000.0',
                'created_at': '2026-01-01T00:00:00Z'
            }
        ]
    }
    
    adapter = RobinhoodExchangeAdapter(mock_client)
    orders = adapter.get_open_orders()
    
    assert len(orders) == 2
    assert orders[0]['id'] == 'order-1'
    assert orders[0]['status'] == 'open'
    assert orders[1]['symbol'] == 'ETH-USD'
    
    mock_client.get_orders.assert_called_once_with(symbol=None, state='open')


def test_get_open_orders_with_symbol():
    """Test filtering open orders by symbol."""
    mock_client = Mock()
    mock_client.get_orders.return_value = {'results': []}
    
    adapter = RobinhoodExchangeAdapter(mock_client)
    adapter.get_open_orders(symbol="BTC-USD")
    
    mock_client.get_orders.assert_called_once_with(symbol="BTC-USD", state='open')


def test_supports_stop_loss():
    """Test that adapter correctly reports no stop-loss support."""
    mock_client = Mock()
    adapter = RobinhoodExchangeAdapter(mock_client)
    
    assert adapter.supports_stop_loss() is False


def test_account_caching():
    """Test that account info is cached to reduce API calls."""
    mock_client = Mock()
    mock_client.get_account.return_value = {
        'results': [{'buying_power': '10000.0'}]
    }
    
    adapter = RobinhoodExchangeAdapter(mock_client)
    
    # First call should hit API
    adapter.get_buying_power()
    assert mock_client.get_account.call_count == 1
    
    # Second immediate call should use cache
    adapter.get_buying_power()
    assert mock_client.get_account.call_count == 1
    
    # Force refresh
    adapter._refresh_account_cache(force=True)
    assert mock_client.get_account.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
