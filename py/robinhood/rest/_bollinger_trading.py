import json
import os
import time
import datetime
import numpy as np
from ._interface import CryptoAPITrading  # Ensure this imports your trading bot class

# Configurations
PRICE_DATA_FILE = "//THO_CLOUD/gavyn/service/btc_price_data.json"
LOG_FILE = "//THO_CLOUD/gavyn/service/trading_log.txt"
BOLLINGER_WINDOW = 20  # 20-period SMA
STD_DEV_MULTIPLIER = 2  # Standard deviations for bands
CHECK_INTERVAL = 60  # Seconds between API checks
TRADE_QUANTITY = "0.00001" # Avoid this being scientific notation
STOP_LOSS_PERCENT = 0.02  # 2% stop-loss
TAKE_PROFIT_PERCENT = 0.04  # 4% take-profit


def log_message(message):
    """Logs messages to a file and prints them."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry + "\n")


def load_price_data():
    """Loads historical price data from the JSON file."""
    if not os.path.exists(PRICE_DATA_FILE):
        return []
    with open(PRICE_DATA_FILE, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []


def save_price_data(new_price_data, max_entries=10000):
    """Saves price data, limiting entries to prevent excessive file size."""
    data = load_price_data()
    data.append(new_price_data)
    data = data[-max_entries:]
    with open(PRICE_DATA_FILE, "w") as file:
        json.dump(data, file, indent=2)


def store_latest_price(api_response):
    """Extracts price data from API response and stores it."""
    if not api_response or "results" not in api_response:
        log_message("❌ Invalid API response")
        return
    result = api_response["results"][0]
    new_price_data = {
        "timestamp": result["timestamp"],
        "symbol": result["symbol"],
        "price": float(result["price"])
    }
    save_price_data(new_price_data)
    log_message(f"✅ Stored price: {new_price_data}")


def calculate_bollinger_bands():
    """Calculates Bollinger Bands based on historical data."""
    data = load_price_data()
    if len(data) < BOLLINGER_WINDOW:
        log_message("⚠️ Not enough historical data for Bollinger Bands calculation.")
        return None, None, None
    prices = np.array([entry["price"] for entry in data[-BOLLINGER_WINDOW:]])
    sma = np.mean(prices)
    std_dev = np.std(prices)
    upper_band = sma + (STD_DEV_MULTIPLIER * std_dev)
    lower_band = sma - (STD_DEV_MULTIPLIER * std_dev)
    return sma, upper_band, lower_band


def trade_based_on_bollinger(api_client, symbol="BTC-USD"):
    """Executes trades based on Bollinger Bands analysis."""
    sma, upper_band, lower_band = calculate_bollinger_bands()
    if sma is None:
        return
    latest_price = load_price_data()[-1]["price"]
    if latest_price <= lower_band:
        log_message("📉 Price hit lower band: Buying")
        api_client.place_market_buy(symbol, TRADE_QUANTITY)
    elif latest_price >= upper_band:
        log_message("📈 Price hit upper band: Selling")
        api_client.place_market_sell(symbol, TRADE_QUANTITY)
    else:
        log_message("⏳ No trade signal.")


def run_trading_bot():
    """Continuously runs the trading bot, checking Bollinger Bands at intervals."""
    api_client = CryptoAPITrading()
    while True:
        try:
            api_response = api_client.get_best_bid_ask("BTC-USD")
            store_latest_price(api_response)
            trade_based_on_bollinger(api_client)
        except Exception as e:
            log_message(f"❌ Error: {e}")
        log_message(f"⏳ Waiting {CHECK_INTERVAL} seconds before next check...\n")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_trading_bot()
