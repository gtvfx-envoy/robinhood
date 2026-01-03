# encoding: utf-8
""""""
import json
import os
import sys
import time
import datetime
import smtplib
from email.mime.text import MIMEText
from ._interface import CryptoAPITrading  # Ensure this imports your trading bot class

# Set UTF-8 encoding for Windows console if supported
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8") # type: ignore[union-attr]

def _get_smtp_settings():
    """ """
    SERVICE_FILE = "//THO_CLOUD/gavyn/service/smtp.json"
    with open(SERVICE_FILE, 'r') as data_file:
        data = json.load(data_file)
    return data

SMTP_SETTINGS = _get_smtp_settings()

SMTP_SERVER = SMTP_SETTINGS.get("server")
SMTP_PORT = SMTP_SETTINGS.get("port")
EMAIL_SENDER = SMTP_SETTINGS.get("sender")
EMAIL_PASSWORD = SMTP_SETTINGS.get("password")
EMAIL_RECIPIENT = SMTP_SETTINGS.get("recipient")


# Configurations
PRICE_DATA_FILE = "//THO_CLOUD/gavyn/service/btc_price_data.json"
TRADE_HISTORY_FILE = "//THO_CLOUD/gavyn/service/btc_trade_history.json"
LOG_FILE = "//THO_CLOUD/gavyn/service/trading_log.txt"

MOMENTUM_THRESHOLD = 0.002  # 0.2% price change triggers a trade
SHORT_TERM_WINDOW = 5
LONG_TERM_WINDOW = 20
CHECK_INTERVAL = 3600  # Seconds between API checks (21600=6 hours, 3600=1 hour)
TRADE_QUANTITY = 0.000961  # BTC quantity per trade
STOP_LOSS_PERCENT = 0.01  # 1% stop-loss
TAKE_PROFIT_PERCENT = 0.02  # 2% take-profit



def log_message(message):
    """Logs messages to a file and prints them."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)

    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry + "\n")


def send_email_alert(subject, body):
    """Sends an email alert for important trade actions."""
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECIPIENT

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())

        log_message(f"📧 Email alert sent: {subject}")

    except Exception as e:
        log_message(f"⚠️ Failed to send email alert: {e}")


def load_json_file(filepath):
    """Loads JSON data from a file or returns an empty list if the file doesn't exist."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []


def save_json_file(filepath, data):
    """Saves data to a JSON file."""
    with open(filepath, "w") as file:
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
        "price": float(result["price"]),
        "bid": float(result["bid_inclusive_of_sell_spread"]),
        "ask": float(result["ask_inclusive_of_buy_spread"])
    }

    price_data = load_json_file(PRICE_DATA_FILE)
    price_data.append(new_price_data)
    price_data = price_data[-20000:]  # Limit entries

    save_json_file(PRICE_DATA_FILE, price_data)
    log_message(f"✅ Stored price: {new_price_data}")


def calculate_momentum():
    """Calculates momentum using short-term and long-term moving averages."""
    data = load_json_file(PRICE_DATA_FILE)
    if len(data) < LONG_TERM_WINDOW:
        log_message("⚠️ Not enough historical data for momentum calculation.")
        return None

    short_term_prices = [entry["price"] for entry in data[-SHORT_TERM_WINDOW:]]
    long_term_prices = [entry["price"] for entry in data[-LONG_TERM_WINDOW:]]

    short_term_avg = sum(short_term_prices) / len(short_term_prices)
    long_term_avg = sum(long_term_prices) / len(long_term_prices)

    momentum = (short_term_avg - long_term_avg) / long_term_avg
    log_message(f"📊 Momentum: {momentum:.5f}")
    return momentum


def get_last_buy_price():
    """Returns the last buy price from the trade history, or None if no buy exists."""
    trades = load_json_file(TRADE_HISTORY_FILE)
    for trade in reversed(trades):  # Iterate from the latest trade
        if trade["type"] == "BUY":
            return trade["price"]
    return None


def record_trade(trade_type, price, quantity):
    """Records trade details in a JSON file and logs the trade."""
    trade_history = load_json_file(TRADE_HISTORY_FILE)
    trade_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "type": trade_type,
        "price": price,
        "quantity": quantity
    }
    trade_history.append(trade_entry)
    save_json_file(TRADE_HISTORY_FILE, trade_history)

    log_message(f"📌 Trade recorded: {trade_entry}")
    send_email_alert(f"{trade_type} Trade Executed", json.dumps(trade_entry, indent=2))


def trade_based_on_momentum(api_client, symbol="BTC-USD"):
    """Executes trades based on momentum and stop-loss/take-profit rules."""
    momentum = calculate_momentum()
    if momentum is None:
        return

    last_price = load_json_file(PRICE_DATA_FILE)[-1]["price"]
    last_buy_price = get_last_buy_price()

    if momentum > MOMENTUM_THRESHOLD:
        log_message("🚀 Positive momentum detected: Buying")
        # api_client.place_market_buy(symbol, TRADE_QUANTITY)
        record_trade("BUY", last_price, TRADE_QUANTITY)

    elif momentum < -MOMENTUM_THRESHOLD:
        log_message("📉 Negative momentum detected: Selling")
        # api_client.place_market_sell(symbol, TRADE_QUANTITY)
        record_trade("SELL", last_price, TRADE_QUANTITY)

    elif last_buy_price:
        price_change = (last_price - last_buy_price) / last_buy_price
        if price_change <= -STOP_LOSS_PERCENT:
            log_message("⛔ Stop-loss triggered: Selling to minimize loss")
            # api_client.place_market_sell(symbol, TRADE_QUANTITY)
            record_trade("SELL", last_price, TRADE_QUANTITY)

        elif price_change >= TAKE_PROFIT_PERCENT:
            log_message("✅ Take-profit triggered: Selling for profit")
            # api_client.place_market_sell(symbol, TRADE_QUANTITY)
            record_trade("SELL", last_price, TRADE_QUANTITY)

    else:
        log_message("⏳ No significant momentum, no trade executed.")


def run_trading_bot():
    """Continuously runs the trading bot, checking momentum at intervals."""
    api_client = CryptoAPITrading()

    while True:
        try:
            api_response = api_client.get_best_bid_ask("BTC-USD")
            store_latest_price(api_response)
            trade_based_on_momentum(api_client)

        except Exception as e:
            log_message(f"❌ Error: {e}")

        log_message(f"⏳ Waiting {CHECK_INTERVAL} seconds before next check...\n")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_trading_bot()
