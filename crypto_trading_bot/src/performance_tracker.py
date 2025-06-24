import pandas as pd
import json
import os
from datetime import datetime

class PerformanceTracker:
    def __init__(self, trade_history_filepath="data/trade_history.json"):
        """
        Initializes the PerformanceTracker.

        Args:
            trade_history_filepath (str): Path to the JSON file for storing trade history.
        """
        self.trade_history_filepath = trade_history_filepath
        self.trades = []
        self.initial_capital = 0.0 # Can be set later
        self.current_portfolio_value = 0.0 # To be updated
        self._load_trade_history()

    def __str__(self):
        """Returns a string representation of the performance tracker."""
        summary = self.get_performance_summary()
        return (f"PerformanceTracker(initial_capital={summary['initial_capital']}, "
                f"total_trades={summary['total_trades']}, "
                f"realized_pnl_simple={summary['realized_pnl_simple']})")
    
    def __repr__(self):
        """Returns a string representation of the performance tracker."""
        return self.__str__()

    def _load_trade_history(self):
        """Loads trade history from the JSON file if it exists."""
        if os.path.exists(self.trade_history_filepath):
            try:
                with open(self.trade_history_filepath, 'r') as f:
                    self.trades = json.load(f)
                print(f"Loaded {len(self.trades)} trades from {self.trade_history_filepath}")
            except json.JSONDecodeError:
                print(f"Error: Could not decode JSON from {self.trade_history_filepath}. Starting with empty history.")
                self.trades = []
            except Exception as e:
                print(f"An unexpected error occurred while loading trade history: {e}. Starting with empty history.")
                self.trades = []
        else:
            print(f"No trade history file found at {self.trade_history_filepath}. Starting with empty history.")
            self.trades = []

    def _save_trade_history(self):
        """Saves the current trade history to the JSON file."""
        try:
            os.makedirs(os.path.dirname(self.trade_history_filepath), exist_ok=True)
            with open(self.trade_history_filepath, 'w') as f:
                json.dump(self.trades, f, indent=4)
            print(f"Saved {len(self.trades)} trades to {self.trade_history_filepath}")
        except Exception as e:
            print(f"An error occurred while saving trade history: {e}")

    def set_initial_capital(self, capital):
        """Sets the initial capital for performance calculations."""
        self.initial_capital = capital
        self.current_portfolio_value = capital # Initially, portfolio value is the capital
        print(f"Initial capital set to: {self.initial_capital}")

    def record_trade(self, symbol, trade_type, quantity, price, timestamp=None):
        """
        Records a trade.

        Args:
            symbol (str): The trading symbol (e.g., 'BTCUSD').
            trade_type (str): 'buy' or 'sell'.
            quantity (float): The amount of the asset traded.
            price (float): The price at which the trade was executed.
            timestamp (str, optional): Timestamp of the trade. Defaults to current time.
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        trade = {
            "timestamp": timestamp,
            "symbol": symbol,
            "type": trade_type,
            "quantity": quantity,
            "price": price,
            "cost_or_proceeds": quantity * price
        }
        self.trades.append(trade)
        self._update_portfolio_value(trade) # Basic update, needs refinement for actual P&L
        self._save_trade_history()
        print(f"Recorded trade: {trade_type} {quantity} {symbol} @ {price}")

    def _update_portfolio_value(self, trade):
        """
        A very basic way to update portfolio value.
        This needs to be more sophisticated, considering assets held.
        For now, it just adds proceeds from sells and subtracts costs from buys from initial capital.
        This is a placeholder for a more robust portfolio valuation.
        """
        if trade['type'] == 'buy':
            # Assuming the 'cost_or_proceeds' for a buy reduces cash available
            # This doesn't track the value of the asset bought, just the cash component.
            pass # More complex logic needed here for actual portfolio value
        elif trade['type'] == 'sell':
            # Assuming 'cost_or_proceeds' for a sell increases cash
            pass # More complex logic needed here

        # This is not a true portfolio value calculation yet.
        # It's more like a running cash balance if we started with cash.

    def calculate_total_pnl(self):
        """
        Calculates the total Profit and Loss.
        This is a simplified P&L based on recorded trades and needs to be
        tied to a proper portfolio valuation method.
        """
        total_pnl = 0.0
        # This is a very naive PnL calculation.
        # A proper PnL would require tracking asset positions and their current market value.
        # For now, let's sum up proceeds from sells and subtract costs from buys.
        # This doesn't account for unrealized P&L.
        for trade in self.trades:
            if trade['type'] == 'sell':
                total_pnl += trade['cost_or_proceeds']
            elif trade['type'] == 'buy':
                total_pnl -= trade['cost_or_proceeds']
        return total_pnl

    def get_performance_summary(self):
        """Returns a summary of the trading performance."""
        total_trades = len(self.trades)
        # Placeholder for more detailed summary
        # current_value = self.current_portfolio_value # Needs proper calculation
        # pnl = current_value - self.initial_capital if self.initial_capital > 0 else 0

        pnl = self.calculate_total_pnl() # Using the simplified PnL for now

        summary = {
            "total_trades": total_trades,
            "initial_capital": self.initial_capital,
            # "current_portfolio_value": current_value, # Needs proper calculation
            "realized_pnl_simple": pnl, # This is a simple realized P&L
            "trade_history_file": self.trade_history_filepath
        }
        return summary

    def get_trades_df(self):
        """Returns the trade history as a pandas DataFrame."""
        return pd.DataFrame(self.trades)

    def export_trade_history(self, filepath):
        """
        Exports the trade history to a CSV file.

        Args:
            filepath (str): Path to the output CSV file.
        """
        df = self.get_trades_df()
        df.to_csv(filepath, index=False)
        print(f"Exported trade history to {filepath}")

    def import_trade_history(self, filepath):
        """
        Imports trade history from a CSV file.

        Args:
            filepath (str): Path to the input CSV file.
        """
        try:
            df = pd.read_csv(filepath)
            for _, row in df.iterrows():
                self.record_trade(
                    symbol=row['symbol'],
                    trade_type=row['type'],
                    quantity=row['quantity'],
                    price=row['price'],
                    timestamp=row['timestamp']
                )
            print(f"Imported {len(df)} trades from {filepath}")
        except Exception as e:
            print(f"An error occurred while importing trade history: {e}")

    def clear_trade_history(self):
        """Clears the trade history."""
        self.trades = []
        self._save_trade_history()
        print("Cleared trade history.")

    def reset(self):
        """Resets the performance tracker, clearing all trades and resetting initial capital."""
        self.trades = []
        self.initial_capital = 0.0
        self.current_portfolio_value = 0.0
        self._save_trade_history()
        print("Performance tracker has been reset.")

    def get_trade_history(self):
        """Returns the trade history."""
        return self.trades
    
    def get_trades_df(self):
        """Returns the trade history as a DataFrame."""
        return pd.DataFrame(self.trades)
