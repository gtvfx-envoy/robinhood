import pandas as pd

class DataProcessor:
    def __init__(self):
        """
        Initializes the DataProcessor.
        May hold state in the future, e.g., a dataframe being processed.
        """
        self.df = None # Optionally, the processor can hold a dataframe

    def load_historical_prices(self, filepath):
        """Loads historical price data from a CSV file."""
        # Option 1: Store df in the instance
        # self.df = pd.read_csv(filepath)
        # return self.df
        # Option 2: Return df directly (more functional, as original)
        return pd.read_csv(filepath)

    def preprocess_data(self, df):
        """Preprocesses the historical price data for analysis."""
        # Operates on the passed df or self.df
        # For consistency with original functions, let's assume df is passed
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        return df

    def calculate_moving_average(self, df, window):
        """Calculates the moving average for the given window."""
        # Assumes 'price' column exists in df
        return df['price'].rolling(window=window).mean()

    def calculate_price_changes(self, df):
        """Calculates daily price changes."""
        # Assumes 'price' column exists in df
        df['price_change'] = df['price'].pct_change()
        return df

    def save_processed_data(self, df, filepath):
        """Saves the processed data to a CSV file."""
        df.to_csv(filepath, index=True)
    
    def load_processed_data(self, filepath):
        """Loads processed data from a CSV file."""
        try:
            df = pd.read_csv(filepath, index_col='timestamp', parse_dates=True)
            return df
        except FileNotFoundError:
            print(f"Error: Processed data file not found at {filepath}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred while loading processed data: {e}")
            return None
        
    def process_data(self, filepath):
        """
        Main method to load, preprocess, and return processed data.
        This is a more functional approach, similar to the original code.
        """
        df = self.load_historical_prices(filepath)
        if df is not None:
            df = self.preprocess_data(df)
            df['moving_average_10'] = self.calculate_moving_average(df, 10)
            df['moving_average_50'] = self.calculate_moving_average(df, 50)
            df = self.calculate_price_changes(df)
            return df
        else:
            print("Failed to load historical prices.")
            return None
        
    def get_latest_price(self, df):
        """Returns the latest price from the processed dataframe."""
        if df is not None and not df.empty:
            return df['price'].iloc[-1]
        else:
            print("Dataframe is empty or not loaded.")
            return None
        
    def get_price_change(self, df):
        """Returns the latest price change from the processed dataframe."""
        if df is not None and 'price_change' in df.columns:
            return df['price_change'].iloc[-1]
        else:
            print("Dataframe is empty or 'price_change' column not found.")
            return None
        
    def get_moving_average(self, df, window):
        """Returns the latest moving average for the specified window."""
        if df is not None and f'moving_average_{window}' in df.columns:
            return df[f'moving_average_{window}'].iloc[-1]
        else:
            print(f"Dataframe is empty or 'moving_average_{window}' column not found.")
            return None
    
    def get_all_moving_averages(self, df):
        """Returns a dictionary of all moving averages in the dataframe."""
        if df is not None:
            moving_averages = {}
            for col in df.columns:
                if 'moving_average' in col:
                    moving_averages[col] = df[col].iloc[-1]
            return moving_averages
        else:
            print("Dataframe is empty or not loaded.")
            return None
    
    def get_all_price_changes(self, df):
        """Returns a dictionary of all price changes in the dataframe."""
        if df is not None and 'price_change' in df.columns:
            return df['price_change'].to_dict()
        else:
            print("Dataframe is empty or 'price_change' column not found.")
            return None
        
    def get_all_prices(self, df):
        """Returns a dictionary of all prices in the dataframe."""
        if df is not None and 'price' in df.columns:
            return df['price'].to_dict()
        else:
            print("Dataframe is empty or 'price' column not found.")
            return None
    
    def get_all_timestamps(self, df):
        """Returns a list of all timestamps in the dataframe."""
        if df is not None and 'timestamp' in df.index.names:
            return df.index.tolist()
        else:
            print("Dataframe is empty or 'timestamp' index not found.")
            return None
    
    def get_all_data(self, df):
        """Returns the entire dataframe as a dictionary."""
        if df is not None:
            return df.to_dict(orient='records')
        else:
            print("Dataframe is empty or not loaded.")
            return None
    
    def get_data_summary(self, df):
        """Returns a summary of the dataframe."""
        if df is not None:
            summary = {
                'shape': df.shape,
                'columns': df.columns.tolist(),
                'head': df.head().to_dict(orient='records'),
                'tail': df.tail().to_dict(orient='records'),
                'description': df.describe().to_dict()
            }
            return summary
        else:
            print("Dataframe is empty or not loaded.")
            return None
    
    def get_data_statistics(self, df):
        """Returns basic statistics of the dataframe."""
        if df is not None:
            stats = {
                'mean': df.mean().to_dict(),
                'median': df.median().to_dict(),
                'std': df.std().to_dict(),
                'min': df.min().to_dict(),
                'max': df.max().to_dict()
            }
            return stats
        else:
            print("Dataframe is empty or not loaded.")
            return None
        
    def get_data_info(self, df):
        """Returns information about the dataframe."""
        if df is not None:
            info = {
                'shape': df.shape,
                'columns': df.columns.tolist(),
                'dtypes': df.dtypes.to_dict(),
                'null_counts': df.isnull().sum().to_dict()
            }
            return info
        else:
            print("Dataframe is empty or not loaded.")
            return None
        
    def get_data_head(self, df, n=5):
        """Returns the first n rows of the dataframe."""
        if df is not None:
            return df.head(n).to_dict(orient='records')
        else:
            print("Dataframe is empty or not loaded.")
            return None
        
    def get_data_tail(self, df, n=5):
        """Returns the last n rows of the dataframe."""
        if df is not None:
            return df.tail(n).to_dict(orient='records')
        else:
            print("Dataframe is empty or not loaded.")
            return None
        
    def get_data_columns(self, df):
        """Returns the columns of the dataframe."""
        if df is not None:
            return df.columns.tolist()
        else:
            print("Dataframe is empty or not loaded.")
            return None
        
    def get_data_shape(self, df):
        """Returns the shape of the dataframe."""
        if df is not None:
            return df.shape
        else:
            print("Dataframe is empty or not loaded.")
            return None
        
    def get_data_index(self, df):
        """Returns the index of the dataframe."""
        if df is not None:
            return df.index.tolist()
        else:
            print("Dataframe is empty or not loaded.")
            return None
        
    def get_data_columns_info(self, df):    
        """Returns information about the columns of the dataframe."""
        if df is not None:
            columns_info = {}
            for col in df.columns:
                columns_info[col] = {
                    'dtype': df[col].dtype,
                    'null_count': df[col].isnull().sum(),
                    'unique_count': df[col].nunique(),
                    'sample_values': df[col].dropna().unique()[:5].tolist()  # Sample first 5 unique values
                }
            return columns_info
        else:
            print("Dataframe is empty or not loaded.")
            return None
        
    def get_data_column_info(self, df, column):
        """Returns information about a specific column in the dataframe."""
        if df is not None and column in df.columns:
            col_info = {
                'dtype': df[column].dtype,
                'null_count': df[column].isnull().sum(),
                'unique_count': df[column].nunique(),
                'sample_values': df[column].dropna().unique()[:5].tolist()  # Sample first 5 unique values
            }
            return col_info
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_statistics(self, df, column):
        """Returns statistics for a specific column in the dataframe."""
        if df is not None and column in df.columns:
            if pd.api.types.is_numeric_dtype(df[column]):
                col_stats = {
                    'mean': df[column].mean(),
                    'median': df[column].median(),
                    'std': df[column].std(),
                    'min': df[column].min(),
                    'max': df[column].max()
                }
            else:
                col_stats = {
                    'unique_count': df[column].nunique(),
                    'sample_values': df[column].dropna().unique()[:5].tolist()  # Sample first 5 unique values
                }
            return col_stats
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_head(self, df, column, n=5):
        """Returns the first n rows of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].head(n).tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_tail(self, df, column, n=5):
        """Returns the last n rows of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].tail(n).tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_unique_values(self, df, column):
        """Returns unique values of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].dropna().unique().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_value_counts(self, df, column):
        """Returns value counts of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].value_counts().to_dict()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_null_counts(self, df, column):
        """Returns the count of null values in a specific column of the dataframe."""
        if df is not None and column in df.columns:
            return df[column].isnull().sum()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_dtype(self, df, column):
        """Returns the data type of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].dtype
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_min(self, df, column):
        """Returns the minimum value of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].min()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_max(self, df, column):
        """Returns the maximum value of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].max()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_mean(self, df, column):
        """Returns the mean value of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].mean()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_median(self, df, column):
        """Returns the median value of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].median()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_std(self, df, column):
        """Returns the standard deviation of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].std()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_quantiles(self, df, column, quantiles=[0.25, 0.5, 0.75]):
        """Returns the quantiles of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].quantile(quantiles).to_dict()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_correlation(self, df, column1, column2):
        """Returns the correlation between two columns in the dataframe."""
        if df is not None and column1 in df.columns and column2 in df.columns:
            return df[column1].corr(df[column2])
        else:
            print(f"One or both columns '{column1}' and '{column2}' not found or dataframe is empty.")
            return None
        
    def get_data_column_covariance(self, df, column1, column2):
        """Returns the covariance between two columns in the dataframe."""
        if df is not None and column1 in df.columns and column2 in df.columns:
            return df[column1].cov(df[column2])
        else:
            print(f"One or both columns '{column1}' and '{column2}' not found or dataframe is empty.")
            return None
        
    def get_data_column_skewness(self, df, column):
        """Returns the skewness of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].skew()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_kurtosis(self, df, column):
        """Returns the kurtosis of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].kurtosis()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_frequency(self, df, column):
        """Returns the frequency of each unique value in a specific column of the dataframe."""
        if df is not None and column in df.columns:
            return df[column].value_counts().to_dict()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_frequency_distribution(self, df, column):
        """Returns the frequency distribution of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].value_counts(normalize=True).to_dict()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_histogram(self, df, column, bins=10):
        """Returns the histogram of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            hist, bin_edges = pd.cut(df[column], bins=bins, retbins=True)
            return hist.value_counts().to_dict(), bin_edges.tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None, None
    
    def get_data_column_boxplot(self, df, column):
        """Returns the boxplot data for a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return {
                'min': df[column].min(),
                'q1': df[column].quantile(0.25),
                'median': df[column].median(),
                'q3': df[column].quantile(0.75),
                'max': df[column].max(),
                'outliers': df[(df[column] < df[column].quantile(0.25) - 1.5 * (df[column].quantile(0.75) - df[column].quantile(0.25))) | 
                               (df[column] > df[column].quantile(0.75) + 1.5 * (df[column].quantile(0.75) - df[column].quantile(0.25)))][column].tolist()
            }
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_outliers(self, df, column):
        """Returns the outliers of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[(df[column] < df[column].quantile(0.25) - 1.5 * (df[column].quantile(0.75) - df[column].quantile(0.25))) | 
                       (df[column] > df[column].quantile(0.75) + 1.5 * (df[column].quantile(0.75) - df[column].quantile(0.25)))][column].tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_mean(self, df, column, window):
        """Returns the rolling mean of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).mean().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_std(self, df, column, window):
        """Returns the rolling standard deviation of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).std().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_min(self, df, column, window):
        """Returns the rolling minimum of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).min().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_max(self, df, column, window):
        """Returns the rolling maximum of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).max().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_sum(self, df, column, window):
        """Returns the rolling sum of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).sum().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_var(self, df, column, window):
        """Returns the rolling variance of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).var().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_corr(self, df, column1, column2, window):
        """Returns the rolling correlation between two columns in the dataframe."""
        if df is not None and column1 in df.columns and column2 in df.columns:
            return df[column1].rolling(window=window).corr(df[column2]).tolist()
        else:
            print(f"One or both columns '{column1}' and '{column2}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_cov(self, df, column1, column2, window):
        """Returns the rolling covariance between two columns in the dataframe."""
        if df is not None and column1 in df.columns and column2 in df.columns:
            return df[column1].rolling(window=window).cov(df[column2]).tolist()
        else:
            print(f"One or both columns '{column1}' and '{column2}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_skew(self, df, column, window):
        """Returns the rolling skewness of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).skew().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_kurt(self, df, column, window):
        """Returns the rolling kurtosis of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).kurt().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_quantiles(self, df, column, window, quantiles=[0.25, 0.5, 0.75]):
        """Returns the rolling quantiles of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).quantile(quantiles).to_dict()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_frequency(self, df, column, window):
        """Returns the rolling frequency of each unique value in a specific column of the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).apply(lambda x: x.value_counts().to_dict(), raw=False).tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_frequency_distribution(self, df, column, window):
        """Returns the rolling frequency distribution of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).apply(lambda x: x.value_counts(normalize=True).to_dict(), raw=False).tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_histogram(self, df, column, window, bins=10):
        """Returns the rolling histogram of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).apply(lambda x: pd.cut(x, bins=bins).value_counts().to_dict(), raw=False).tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_boxplot(self, df, column, window):
        """Returns the rolling boxplot data for a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).apply(lambda x: {
                'min': x.min(),
                'q1': x.quantile(0.25),
                'median': x.median(),
                'q3': x.quantile(0.75),
                'max': x.max(),
                'iqr': x.quantile(0.75) - x.quantile(0.25)
            })
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_outliers(self, df, column, window):
        """Returns the rolling outliers of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].rolling(window=window).apply(lambda x: x.value_counts(normalize=True)[x.quantile(0.75) - x.quantile(0.25) > 1.5].to_dict(), raw=False).tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
    
    def get_data_column_rolling_ewm(self, df, column, span):
        """Returns the exponentially weighted moving average of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].ewm(span=span).mean().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_ewm_std(self, df, column, span):
        """Returns the exponentially weighted moving standard deviation of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].ewm(span=span).std().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_ewm_min(self, df, column, span):
        """Returns the exponentially weighted moving minimum of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].ewm(span=span).min().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_ewm_max(self, df, column, span):
        """Returns the exponentially weighted moving maximum of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].ewm(span=span).max().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_ewm_sum(self, df, column, span):
        """Returns the exponentially weighted moving sum of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].ewm(span=span).sum().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_ewm_var(self, df, column, span):
        """Returns the exponentially weighted moving variance of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].ewm(span=span).var().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_ewm_skew(self, df, column, span):
        """Returns the exponentially weighted moving skew of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].ewm(span=span).skew().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        
    def get_data_column_rolling_ewm_kurt(self, df, column, span):
        """Returns the exponentially weighted moving kurtosis of a specific column in the dataframe."""
        if df is not None and column in df.columns:
            return df[column].ewm(span=span).kurt().tolist()
        else:
            print(f"Column '{column}' not found or dataframe is empty.")
            return None
        