import time
from trading_bot import TradingBot

def main():
    trading_bot = TradingBot()
    trading_bot.initialize()
    
    while True:
        trading_bot.run()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()