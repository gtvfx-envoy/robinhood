class TradingBot:
    def __init__(self, api_client, data_processor, notifier, performance_tracker, ml_model):
        self.api_client = api_client
        self.data_processor = data_processor
        self.notifier = notifier
        self.performance_tracker = performance_tracker
        self.ml_model = ml_model
        self.trade_history = []

    def load_historical_data(self, filepath):
        self.data_processor.load_data(filepath)

    def analyze_data(self):
        processed_data = self.data_processor.process_data()
        return processed_data

    def make_trade_decision(self, processed_data):
        signal = self.ml_model.predict(processed_data)
        return signal

    def execute_trade(self, signal):
        if signal == "BUY":
            self.api_client.place_market_order("buy", "BTC-USD", 0.001)  # Example trade
            self.trade_history.append({"action": "BUY", "price": self.api_client.get_current_price("BTC-USD")})
            self.notifier.send_alert("BUY Trade Executed", f"Bought BTC-USD at {self.api_client.get_current_price('BTC-USD')}")
        elif signal == "SELL":
            self.api_client.place_market_order("sell", "BTC-USD", 0.001)  # Example trade
            self.trade_history.append({"action": "SELL", "price": self.api_client.get_current_price("BTC-USD")})
            self.notifier.send_alert("SELL Trade Executed", f"Sold BTC-USD at {self.api_client.get_current_price('BTC-USD')}")

    def track_performance(self):
        self.performance_tracker.log_trade_history(self.trade_history)

    def run(self):
        self.load_historical_data("data/historical_prices.csv")
        processed_data = self.analyze_data()
        signal = self.make_trade_decision(processed_data)
        self.execute_trade(signal)
        self.track_performance()