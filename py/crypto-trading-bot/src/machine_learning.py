import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

def load_historical_data(filepath):
    """Loads historical price data from a CSV file."""
    return pd.read_csv(filepath)

def preprocess_data(data):
    """Prepares the data for training by creating features and labels."""
    data['Price_Change'] = data['Close'].pct_change()
    data['Target'] = (data['Price_Change'] > 0).astype(int)
    data.dropna(inplace=True)
    features = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    labels = data['Target']
    return features, labels

def train_model(features, labels):
    """Trains a machine learning model using the provided features and labels."""
    X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    print(f"Model accuracy: {accuracy:.2f}")
    return model

def save_model(model, filepath):
    """Saves the trained model to a file."""
    joblib.dump(model, filepath)

def load_model(filepath):
    """Loads a trained model from a file."""
    return joblib.load(filepath)

def predict(model, features):
    """Makes predictions using the trained model."""
    return model.predict(features)