from typing import Any, Dict

class Endpoints:
    BASE_URL = "https://api.robinhood.com"

    @staticmethod
    def get_historical_prices(symbol: str) -> str:
        return f"{Endpoints.BASE_URL}/marketdata/{symbol}/historical/"

    @staticmethod
    def get_current_price(symbol: str) -> str:
        return f"{Endpoints.BASE_URL}/quotes/{symbol}/"

    @staticmethod
    def place_order() -> str:
        return f"{Endpoints.BASE_URL}/orders/"

    @staticmethod
    def get_order(order_id: str) -> str:
        return f"{Endpoints.BASE_URL}/orders/{order_id}/"

    @staticmethod
    def get_open_orders() -> str:
        return f"{Endpoints.BASE_URL}/orders/?state=open"

    @staticmethod
    def cancel_order(order_id: str) -> str:
        return f"{Endpoints.BASE_URL}/orders/{order_id}/cancel/"

    @staticmethod
    def get_account() -> str:
        return f"{Endpoints.BASE_URL}/accounts/"

    @staticmethod
    def get_positions() -> str:
        return f"{Endpoints.BASE_URL}/positions/"