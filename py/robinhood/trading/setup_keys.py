"""
Setup script for encrypting and storing Robinhood API credentials.

This script helps you securely store your Robinhood API key and private key
using encryption.
"""

__all__ = [
    "get_keys",
    "setup_keys"
    ]

import json
import os
import sys

from pathlib import Path

from .key_manager import setup_encrypted_storage


def get_keys() -> tuple:
    """Retrieve API keys from the service key file."""
    SERVICE_KEY_FILE = Path(os.getenv("SERVICE_ROOT", "")) / "robinhood.json"

    if not SERVICE_KEY_FILE.exists():
        raise FileNotFoundError(f"Service key file not found at {SERVICE_KEY_FILE}")

    with open(SERVICE_KEY_FILE, 'r') as key_file:
        data = json.load(key_file)

    return data.get("private_key"), data.get("public_key"), data.get("api_key")


def setup_keys():
    """Interactive setup for Robinhood API credentials."""
    
    print("="*70)
    print("Robinhood API Credentials Setup")
    print("="*70)
    print()
    print("This script will help you encrypt and store your Robinhood API credentials.")
    print()
    
    # Load credentials from JSON file (will raise if not found)
    private_key, public_key, api_key = get_keys()
    print(f"✓ Loaded credentials from service key file")
    print(f"  API Key: {api_key}")
    print(f"  Private Key: {private_key[:20]}...")
    print()
    
    print()
    print("Choose encryption method:")
    print("  1. File-based encryption (separate cipher key file)")
    print("  2. Password-based encryption (requires password)")
    print()
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        method = 'file'
    elif choice == "2":
        method = 'password'
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)
    
    print()
    print("Setting up encryption...")
    
    try:
        setup_encrypted_storage(api_key, private_key, method=method)
        print()
        print("="*70)
        print("✓ Setup complete!")
        print("="*70)
        print()
        print("Your credentials are now securely encrypted.")
        print("You can now use the Robinhood API client in your code.")
        
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_keys()
