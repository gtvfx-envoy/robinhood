from typing import Any, Dict
import json
import requests

class RobinhoodAuthenticator:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.authenticated = False

    def authenticate(self) -> bool:
        """Authenticates the user with the Robinhood API."""
        url = "https://api.robinhood.com/oauth2/token/"
        payload = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "client_id": "your_client_id",  # Replace with your actual client ID
            "client_secret": "your_client_secret"  # Replace with your actual client secret
        }
        response = self.session.post(url, data=payload)

        if response.status_code == 200:
            self.authenticated = True
            self.session.headers.update({
                "Authorization": f"Bearer {response.json()['access_token']}"
            })
            return True
        else:
            print("Authentication failed:", response.json())
            return False

    def is_authenticated(self) -> bool:
        """Checks if the user is authenticated."""
        return self.authenticated

    def logout(self) -> None:
        """Logs out the user by clearing the session."""
        self.session.close()
        self.authenticated = False