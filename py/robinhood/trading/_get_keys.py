"""Module to retrieve Coinbase API keys from a service key file."""

__all__ = [
    "get_keys",
    "setup_keys"
    ]

import json
import os
from pathlib import Path

from coinbase_trading.key_manager import KeyManager, setup_encrypted_storage


def get_keys(read_only: bool = True) -> tuple:
    """Retrieve API keys from the service key file."""
    SERVICE_KEY_FILE = Path(os.getenv("SERVICE_ROOT", "")) / "coinbase.json"

    if not SERVICE_KEY_FILE.exists():
        raise FileNotFoundError(f"Service key file not found at {SERVICE_KEY_FILE}")

    with open(SERVICE_KEY_FILE, 'r') as key_file:
        data = json.load(key_file)
    if read_only:
        return data.get("read-only").get("api_key"), data.get("read-only").get("private_key")
    else:
        return data.get("trading").get("api_key"), data.get("trading").get("private_key")


def setup_keys(read_only: bool = True) -> KeyManager:
    """Set up the KeyManager with encrypted storage using the retrieved keys."""
    # Retrieve keys from your service key file (or modify to load from your local source)
    api_key_name, private_key = get_keys(read_only=read_only)

    # Option A: File-based encryption (creates separate key file)
    return setup_encrypted_storage(api_key_name, private_key, method='file')
