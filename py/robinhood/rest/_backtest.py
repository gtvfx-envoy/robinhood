import json
import datetime

# Configuration
INITIAL_BALANCE = 1000  # Start with $1000
TRADING_FEE = 0.06  # 0.6% trading fee
MOMENTUM_THRESHOLD = 0.002  # Increased threshold
SHORT_TERM_WINDOW = 10
LONG_TERM_WINDOW = 50
STOP_LOSS_PERCENT = 0.01  # 1% stop loss
TAKE_PROFIT_PERCENT = 0.02  # 2% take profit

PRICE_DATA_FILE = "//THO_CLOUD/gavyn/service/btc_price_data.json"

def load_price_data():
    """Loads historical price data for backtesting."""
    with open(PRICE_DATA_FILE, "r") as file:
        return json.load(file)

def backtest_momentum_trading():
    """Runs a backtest of the momentum trading strategy on historical data."""
    data = load_price_data()
    if len(data) < LONG_TERM_WINDOW:
        print("Not enough historical data for backtesting.")
        return

    balance = INITIAL_BALANCE  # Start with cash balance
    btc_holding = 0  # Start with no BTC
    trade_log = []  # Store executed trades

    for i in range(LONG_TERM_WINDOW, len(data)):
        short_term_prices = [entry["price"] for entry in data[i-SHORT_TERM_WINDOW:i]]
        long_term_prices = [entry["price"] for entry in data[i-LONG_TERM_WINDOW:i]]

        short_term_avg = sum(short_term_prices) / len(short_term_prices)
        long_term_avg = sum(long_term_prices) / len(long_term_prices)
        momentum = (short_term_avg - long_term_avg) / long_term_avg

        current_price = data[i]["price"]
        timestamp = data[i]["timestamp"]
        quantity = 0.0001

        if momentum > MOMENTUM_THRESHOLD and balance >= current_price * quantity:
            # Buy BTC
            btc_holding += quantity
            entry_price = current_price
            cost = current_price * quantity * (1 + TRADING_FEE)
            balance -= cost
            trade_log.append((timestamp, "BUY", quantity, current_price))
            print(f"[{timestamp}] BUY {quantity} BTC at ${current_price:.2f}")

        elif btc_holding >= quantity:
            # Check stop-loss or take-profit before selling
            price_change = (current_price - entry_price) / entry_price
            if momentum < -MOMENTUM_THRESHOLD or price_change <= -STOP_LOSS_PERCENT or price_change >= TAKE_PROFIT_PERCENT:
                # Sell BTC
                btc_holding -= quantity
                revenue = current_price * quantity * (1 - TRADING_FEE)
                balance += revenue
                trade_log.append((timestamp, "SELL", quantity, current_price))
                print(f"[{timestamp}] SELL {quantity} BTC at ${current_price:.2f}")

    # Final portfolio value
    final_value = balance + (btc_holding * data[-1]["price"])
    profit = final_value - INITIAL_BALANCE

    print("\n--- Backtest Summary ---")
    print(f"Initial Balance: ${INITIAL_BALANCE:.2f}")
    print(f"Final Portfolio Value: ${final_value:.2f}")
    print(f"Total Profit: ${profit:.2f}")
    print(f"Total Trades: {len(trade_log)}")

    return trade_log

if __name__ == "__main__":
    trade_log = backtest_momentum_trading()
