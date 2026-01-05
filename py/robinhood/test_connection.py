"""
Test script to verify Robinhood API connection.
"""
import sys
from pathlib import Path

# Add the robinhood module to path
sys.path.insert(0, str(Path(__file__).parent))

from .trading import RobinhoodClient, KeyManager, setup_encrypted_storage
from .trading.setup_keys import get_keys


def test_connection():
    """Test connection to Robinhood API."""
    
    print("="*70)
    print("Robinhood API Connection Test")
    print("="*70)
    print()
    
    # Step 1: Check if we have encrypted keys
    manager = KeyManager()
    
    try:
        cipher_key = manager.load_cipher_key()
        print("✓ Found existing encrypted keys")
    except FileNotFoundError:
        print("No encrypted keys found. Setting up now...")
        print()
        
        # Load from JSON and encrypt
        try:
            private_key, public_key, api_key = get_keys()
            print(f"✓ Loaded keys from service file")
            print(f"  API Key: {api_key}")
            print()
            
            # Encrypt with file-based method (simpler for testing)
            setup_encrypted_storage(api_key, private_key, method='file')
            print("✓ Keys encrypted and saved")
            print()
            
            # Now load the cipher key
            cipher_key = manager.load_cipher_key()
            
        except Exception as e:
            print(f"❌ Error during setup: {e}")
            return False
    
    print("Step 1: Creating API client...")
    try:
        client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)
        print("✓ Client created successfully")
        print()
    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        return False
    
    # Step 2: Test API connection by getting account info
    print("Step 2: Retrieving account information...")
    try:
        account = client.get_account()
        print("✓ Successfully connected to Robinhood API!")
        print()
        print("Account Information:")
        print(f"  Account ID: {account.get('id', 'N/A')}")
        print(f"  Status: {account.get('status', 'N/A')}")
        print(f"  Buying Power: ${account.get('buying_power', 'N/A')}")
        print(f"  Cash: ${account.get('cash', 'N/A')}")
        print(f"  Cash Held for Orders: ${account.get('cash_held_for_orders', 'N/A')}")
        print()
        return True
        
    except Exception as e:
        print(f"❌ Failed to retrieve account info: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print("="*70)


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
