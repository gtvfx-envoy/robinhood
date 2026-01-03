# Crypto Trading Bot

This project is a cryptocurrency trading bot that utilizes the Robinhood Crypto REST API to automate trading based on historical price data and machine learning predictions. The bot aggregates historical prices, implements trading strategies, and sends alerts for trading actions.

## Features

- **Historical Price Aggregation**: Collects and stores historical price data for cryptocurrencies.
- **Machine Learning Integration**: Utilizes machine learning models to predict price movements and inform trading decisions.
- **Real-Time Tracking**: Monitors active trades and calculates real-time profit and loss.
- **Notifications**: Sends alerts via text messages or emails regarding trading actions.
- **Performance Metrics**: Logs and calculates performance metrics, including profit and loss.

## Project Structure

```
crypto-trading-bot
├── src
│   ├── main.py                # Entry point of the application
│   ├── trading_bot.py         # Trading logic and strategy management
│   ├── data_processing.py      # Data loading and processing functions
│   ├── machine_learning.py      # Machine learning training and prediction functions
│   ├── notifications.py         # Alert sending functions
│   ├── performance_metrics.py   # Performance logging and calculation functions
│   ├── real_time_tracking.py    # Real-time profit and loss tracking functions
│   ├── utils.py                # Utility functions
│   └── robinhood_api
│       ├── __init__.py        # Initializes the Robinhood API module
│       ├── api_client.py      # Handles API requests to the Robinhood Crypto REST API
│       ├── authentication.py   # Authentication functions for the Robinhood API
│       └── endpoints.py        # Defines API endpoints for trading operations
├── data
│   ├── historical_prices.csv   # Stores historical price data for cryptocurrencies
│   ├── trade_history.json       # Logs the history of trades executed by the bot
│   └── logs
│       └── trading_log.txt      # Contains logs of the trading bot's activities
├── models
│   └── trained_model.pkl        # Stores the trained machine learning model
├── requirements.txt             # Lists project dependencies
├── README.md                    # Project documentation
└── .gitignore                   # Specifies files to ignore by Git
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd crypto-trading-bot
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure the Robinhood API credentials in the `src/robinhood_api/authentication.py` file.

4. Run the trading bot:
   ```
   python src/main.py
   ```

## Usage

The bot will automatically start trading based on the defined strategies and send notifications for any trading actions taken. You can monitor the logs in `data/logs/trading_log.txt` for detailed activity.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or features you'd like to add.

## License

This project is licensed under the MIT License.