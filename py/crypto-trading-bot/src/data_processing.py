import pandas as pd

def load_historical_prices(filepath):
    """Loads historical price data from a CSV file."""
    return pd.read_csv(filepath)

def preprocess_data(df):
    """Preprocesses the historical price data for analysis."""
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    return df

def calculate_moving_average(df, window):
    """Calculates the moving average for the given window."""
    return df['price'].rolling(window=window).mean()

def calculate_price_changes(df):
    """Calculates daily price changes."""
    df['price_change'] = df['price'].pct_change()
    return df

def save_processed_data(df, filepath):
    """Saves the processed data to a CSV file."""
    df.to_csv(filepath, index=True)