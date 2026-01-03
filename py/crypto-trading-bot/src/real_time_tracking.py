import pandas as pd
import json
import time
from datetime import datetime
from .robinhood_api.api_client import ApiClient

class RealTimeTracker:
    def __init__(self, api_client: ApiClient, trade_history_file: str):
        self.api_client = api_client
        self.trade_history_file = trade_history_file
        self.active_trades = {}

    def track_profit_loss(self):
        while True:
            for trade_id, trade_info in self.active_trades.items():
                current_price = self.api_client.get_current_price(trade_info['symbol'])
                profit_loss = (current_price - trade_info['entry_price']) * trade_info['quantity']
                trade_info['profit_loss'] = profit_loss
                self.log_trade(trade_id, trade_info)

            time.sleep(60)  # Check every minute

    def log_trade(self, trade_id, trade_info):
        trade_history = self.load_trade_history()
        trade_info['timestamp'] = datetime.now().isoformat()
        trade_history[trade_id] = trade_info

        with open(self.trade_history_file, 'w') as file:
            json.dump(trade_history, file, indent=2)

    def load_trade_history(self):
        try:
            with open(self.trade_history_file, 'r') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def add_trade(self, trade_id, symbol, entry_price, quantity):
        self.active_trades[trade_id] = {
            'symbol': symbol,
            'entry_price': entry_price,
            'quantity': quantity,
            'profit_loss': 0
        }