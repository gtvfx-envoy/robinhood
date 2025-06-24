def calculate_profit_loss(trade_history):
    total_profit_loss = 0.0
    for trade in trade_history:
        if trade['type'] == 'SELL':
            total_profit_loss += (trade['price'] - trade['buy_price']) * trade['quantity']
    return total_profit_loss

def log_performance_metrics(trade_history, log_file):
    total_profit_loss = calculate_profit_loss(trade_history)
    with open(log_file, 'a') as file:
        file.write(f"Total Profit/Loss: {total_profit_loss:.2f}\n")

def calculate_win_rate(trade_history):
    wins = sum(1 for trade in trade_history if trade['type'] == 'SELL' and (trade['price'] - trade['buy_price']) > 0)
    total_trades = len(trade_history)
    return wins / total_trades if total_trades > 0 else 0

def log_win_rate(trade_history, log_file):
    win_rate = calculate_win_rate(trade_history)
    with open(log_file, 'a') as file:
        file.write(f"Win Rate: {win_rate:.2%}\n")