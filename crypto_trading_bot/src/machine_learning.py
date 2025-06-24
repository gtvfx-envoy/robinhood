# File: py/crypto-trading-bot/src/machine_learning.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib
import os

# Original functions (can be kept for standalone use or refactored/removed)
def load_historical_data(filepath):
    """Loads historical price data from a CSV file."""
    if not os.path.exists(filepath):
        print(f"Error: Historical data file not found at {filepath}")
        return None
    try:
        return pd.read_csv(filepath)
    except Exception as e:
        print(f"Error loading historical data from {filepath}: {e}")
        return None

def preprocess_data_for_ml(data_df): # Renamed to avoid conflict if a class method is also named preprocess_data
    """Prepares the data for training by creating features and labels."""
    if data_df is None or data_df.empty:
        print("Error: Data for preprocessing is empty or None.")
        return None, None
    
    # Ensure required columns are present
    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not all(col in data_df.columns for col in required_columns):
        print(f"Error: Dataframe must contain columns: {required_columns}")
        return None, None

    data_df = data_df.copy() # Avoid SettingWithCopyWarning
    data_df['Price_Change'] = data_df['Close'].pct_change()
    data_df['Target'] = (data_df['Price_Change'] > 0).astype(int)
    data_df.dropna(inplace=True)

    if data_df.empty:
        print("Error: Dataframe is empty after preprocessing (dropna).")
        return None, None
        
    features = data_df[['Open', 'High', 'Low', 'Close', 'Volume']]
    labels = data_df['Target']
    return features, labels

def train_new_model(features, labels): # Renamed to avoid conflict
    """Trains a machine learning model using the provided features and labels."""
    if features is None or labels is None or features.empty or labels.empty:
        print("Error: Features or labels are empty or None for training.")
        return None
    
    X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)
    if X_train.empty or y_train.empty:
        print("Error: Training set is empty after split. Not enough data or too small test_size.")
        return None

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    if not X_test.empty:
        predictions = model.predict(X_test)
        accuracy = accuracy_score(y_test, predictions)
        print(f"Model accuracy on test set: {accuracy:.2f}")
    else:
        print("Test set is empty. Cannot evaluate accuracy. Model trained on all available data.")
    return model

def save_trained_model(model, filepath): # Renamed to avoid conflict
    """Saves the trained model to a file."""
    if model is None:
        print("Error: No model to save.")
        return
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump(model, filepath)
        print(f"Model saved to {filepath}")
    except Exception as e:
        print(f"Error saving model to {filepath}: {e}")

def load_trained_model(filepath): # Renamed to avoid conflict
    """Loads a trained model from a file."""
    if not os.path.exists(filepath):
        print(f"Error: Model file not found at {filepath}")
        return None
    try:
        model = joblib.load(filepath)
        print(f"Model loaded from {filepath}")
        return model
    except Exception as e:
        print(f"Error loading model from {filepath}: {e}")
        return None

def make_prediction(model, features_df): # Renamed to avoid conflict
    """Makes predictions using the trained model."""
    if model is None:
        print("Error: Model is not loaded or trained.")
        return None
    if features_df is None or features_df.empty:
        print("Error: Features DataFrame for prediction is empty or None.")
        return None
    try:
        return model.predict(features_df)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return None

class MachineLearningModel:
    def __init__(self, model_filepath="data/ml_models/price_predictor.joblib"):
        """
        Initializes the MachineLearningModel.

        Args:
            model_filepath (str): Path to store/load the trained model.
        """
        self.model_filepath = model_filepath
        self.model = None
        self._ensure_model_dir_exists()

    def _ensure_model_dir_exists(self):
        """Ensures the directory for storing the model exists."""
        os.makedirs(os.path.dirname(self.model_filepath), exist_ok=True)

    def load_model(self, filepath=None):
        """
        Loads a pre-trained model from the specified filepath or the default one.
        Returns True if successful, False otherwise.
        """
        load_path = filepath if filepath else self.model_filepath
        self.model = load_trained_model(load_path)
        return self.model is not None

    def save_model(self, filepath=None):
        """Saves the current model to the specified filepath or the default one."""
        if self.model is None:
            print("No model to save. Train or load a model first.")
            return False
        save_path = filepath if filepath else self.model_filepath
        save_trained_model(self.model, save_path)
        return True # Assuming save_trained_model handles its own errors for now

    def train_model(self, historical_data_filepath, features_columns=None, target_column=None):
        """
        Loads historical data, preprocesses it, and trains a new model.
        The trained model is stored in self.model and saved.

        Args:
            historical_data_filepath (str): Path to the CSV file with historical data.
            features_columns (list, optional): List of column names to use as features.
                                               Defaults to ['Open', 'High', 'Low', 'Close', 'Volume'].
            target_column (str, optional): The name of the target variable after preprocessing.
                                           Defaults to 'Target' (price increase 0 or 1).

        Returns:
            bool: True if training was successful, False otherwise.
        """
        print(f"Starting model training using data from: {historical_data_filepath}")
        data_df = load_historical_data(historical_data_filepath)
        if data_df is None:
            return False

        # Using the standalone preprocess_data_for_ml function
        features, labels = preprocess_data_for_ml(data_df)
        if features is None or labels is None:
            print("Failed to preprocess data for training.")
            return False

        print(f"Training model with {len(features)} samples.")
        # Using the standalone train_new_model function
        self.model = train_new_model(features, labels)
        
        if self.model:
            print("Model training completed.")
            self.save_model()
            return True
        else:
            print("Model training failed.")
            return False

    def predict(self, current_features_df):
        """
        Makes a prediction based on the current features.
        The input `current_features_df` should be a DataFrame with the same
        feature columns the model was trained on (e.g., ['Open', 'High', 'Low', 'Close', 'Volume']).

        Args:
            current_features_df (pd.DataFrame): DataFrame containing the features for prediction.
                                                It should have one row for a single prediction or multiple rows.

        Returns:
            numpy.ndarray or None: Prediction result (e.g., [0] or [1]), or None if prediction fails.
        """
        if self.model is None:
            print("Model not loaded or trained. Cannot predict.")
            # Attempt to load the model if not already loaded
            if not self.load_model():
                 print("Failed to load a model for prediction.")
                 return None

        if not isinstance(current_features_df, pd.DataFrame):
            print("Error: Input features for prediction must be a pandas DataFrame.")
            return None
            
        # Ensure columns are in the same order as training, if known, or rely on column names
        # For RandomForest, column order doesn't strictly matter as long as names are consistent.
        # However, it's good practice. The standalone `make_prediction` handles this.

        # Using the standalone make_prediction function
        return make_prediction(self.model, current_features_df)

    def get_latest_features_for_prediction(self, data_df):
        """
        Extracts the latest row of features from a DataFrame for prediction.
        Assumes data_df has 'Open', 'High', 'Low', 'Close', 'Volume' columns.

        Args:
            data_df (pd.DataFrame): DataFrame with historical or current market data.

        Returns:
            pd.DataFrame or None: A single-row DataFrame with the latest features, or None.
        """
        if data_df is None or data_df.empty:
            print("Data for feature extraction is empty.")
            return None
        
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in data_df.columns for col in required_cols):
            print(f"Missing one or more required columns for feature extraction: {required_cols}")
            return None
            
        # Get the latest row and select feature columns
        latest_data = data_df.iloc[-1:] # Keep as DataFrame
        features_for_prediction = latest_data[required_cols]
        return features_for_prediction

    def retrain_model(self, historical_data_filepath):
        """
        Retrains the model using the latest historical data.
        This is a convenience method that calls train_model with the current model filepath.

        Args:
            historical_data_filepath (str): Path to the CSV file with historical data.

        Returns:
            bool: True if retraining was successful, False otherwise.
        """
        print("Retraining model with new historical data.")
        return self.train_model(historical_data_filepath, 
                                features_columns=['Open', 'High', 'Low', 'Close', 'Volume'],
                                target_column='Target')
    
# Example usage:
# if __name__ == "__main__":
#     ml_model = MachineLearningModel()
#     if ml_model.train_model("data/historical_prices.csv"):
#         print("Model trained successfully.")
#     else: 
#         print("Failed to train the model.")
#     # To make a prediction, you would typically load the latest market data
#     # and extract the features using get_latest_features_for_prediction.
#     # features_df = ml_model.get_latest_features_for_prediction(latest_market_data_df)
#     # prediction = ml_model.predict(features_df)
#     # print(f"Prediction: {prediction}") 
#     # Note: The above example usage is commented out to avoid execution in a module context.
#     # You would need to implement the logic to load the latest market data and make predictions.
#     # Here's a simple example of how you might do that:
#     # latest_market_data_df = load_latest_market_data()
#     # features_df = ml_model.get_latest_features_for_prediction(latest_market_data_df)
#     # prediction = ml_model.predict(features_df)
#     # print(f"Prediction: {prediction}")
