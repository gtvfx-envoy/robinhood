import time
import os

# Assuming these are the correct relative paths
from .trading_bot import TradingBot
from .robinhood_api.api_client import ApiClient # Path to your ApiClient
from .data_processing import DataProcessor
from .notifications import Notifier
from .performance_tracker import PerformanceTracker
from .machine_learning import MachineLearningModel

def main(iterations: int | None = 1):
    print("Initializing trading bot components...")

    # --- Configuration Notes ---
    # The ApiClient (from py/crypto-trading-bot/src/robinhood_api/api_client.py)
    # loads its API_KEY and BASE64_PRIVATE_KEY internally from a JSON file:
    # specified by SERVICE_KEY_FILE = "//THO_CLOUD/gavyn/service/robinhood.json".
    # Ensure this file exists and is correctly formatted for ApiClient to work.
    # No explicit configuration needs to be passed to its constructor.

    # File paths for other components
    trade_history_filepath = "data/trade_history.json"
    ml_model_filepath = "data/ml_models/price_predictor.joblib"
    # Ensure you have historical data for training if the model doesn't exist
    # Example: "data/historical_data/your_crypto_data.csv"
    # This CSV should contain 'Open', 'High', 'Low', 'Close', 'Volume' columns.
    historical_data_for_ml_training = "data/historical_data/your_crypto_data.csv"


    # --- Instantiate Dependencies ---
    print("Instantiating API client...")
    # ApiClient() takes no arguments as per its definition in
    # py/crypto-trading-bot/src/robinhood_api/api_client.py
    api_client = ApiClient()

    print("Instantiating DataProcessor...")
    data_processor = DataProcessor()
    
    print("Instantiating Notifier...")
    # Notifier will attempt to load SMTP settings via its internal _get_smtp_settings
    # if specific settings are not passed to its constructor.
    notifier = Notifier() 
    
    print("Instantiating PerformanceTracker...")
    performance_tracker = PerformanceTracker(trade_history_filepath=trade_history_filepath)
    # Optionally set initial capital
    # performance_tracker.set_initial_capital(10000.0) # Example: $10,000

    print("Instantiating MachineLearningModel...")
    ml_model = MachineLearningModel(model_filepath=ml_model_filepath)

    # --- Machine Learning Model Handling ---
    if not ml_model.load_model():
        print(f"Could not load ML model from {ml_model_filepath}. Attempting to train a new model.")
        if os.path.exists(historical_data_for_ml_training):
            if ml_model.train_model(historical_data_filepath=historical_data_for_ml_training):
                print("New ML model trained successfully.")
            else:
                print("Failed to train a new ML model. Bot will run without ML predictions if strategy allows.")
        else:
            print(f"Historical data for training not found at {historical_data_for_ml_training}.")
            print("Bot will run without ML predictions if strategy allows.")
    else:
        print(f"ML model loaded successfully from {ml_model_filepath}.")

    # --- Instantiate TradingBot with Dependencies ---
    print("Instantiating TradingBot...")
    trading_bot = TradingBot(
        api_client=api_client,
        data_processor=data_processor,
        notifier=notifier,
        performance_tracker=performance_tracker,
        ml_model=ml_model,
        # Add any other configuration parameters your TradingBot might need
        # e.g., symbol_to_trade="BTCUSD", strategy_name="ml_basic"
    )
    
    print("Initializing TradingBot...")
    # Ensure your TradingBot has an initialize method if you call it here
    if hasattr(trading_bot, 'initialize') and callable(getattr(trading_bot, 'initialize')):
        trading_bot.initialize() 
    else:
        print("TradingBot does not have an initialize method. Skipping.")

    print("Starting TradingBot main loop...")
    try:
        count = 0
        while iterations is None or count < iterations:
            # Ensure your TradingBot has a run method
            if hasattr(trading_bot, 'run') and callable(getattr(trading_bot, 'run')):
                trading_bot.run() 
            else:
                print("TradingBot does not have a run method. Exiting loop.")
                break
            # Consider making the sleep duration configurable
            time.sleep(60)  # Check/run trading logic every minute
            count += 1
    except KeyboardInterrupt:
        print("\nTrading bot stopped by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"An unexpected error occurred in the main loop: {e}")
        # Consider using the notifier for critical errors:
        # notifier.send_email("Trading Bot Critical Failure", f"The bot stopped due to: {e}")
    finally:
        print("Trading bot shutting down.")
        # Example: saving final performance summary
        # summary = performance_tracker.get_performance_summary()
        # print(f"Final Performance Summary: {summary}")


if __name__ == "__main__":
    # Create data directories if they don't exist to prevent errors on first run
    os.makedirs("data/logs", exist_ok=True)
    os.makedirs("data/ml_models", exist_ok=True)
    os.makedirs("data/historical_data", exist_ok=True) # For placing training data

    main(iterations=None)
