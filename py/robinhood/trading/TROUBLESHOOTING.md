# Troubleshooting: Robinhood Integration

Common issues and solutions when using the Robinhood + trading_bot integration.

---

## Error: `InvalidToken` or "Failed to decrypt credentials"

**Problem:**
```python
cryptography.fernet.InvalidToken
# or
ValueError: Failed to decrypt credentials. This usually means:
  1. Wrong password - use the password you set during setup
```

**Causes:**
1. ❌ Using the literal string `"your_password"` (it's just a placeholder!)
2. ❌ Wrong password entered
3. ❌ Credentials not set up yet

**Solution:**

### Step 1: Check if credentials are set up
```python
from robinhood.trading import KeyManager
from pathlib import Path

manager = KeyManager()
if not manager.key_file.exists():
    print("❌ Credentials not found!")
    print(f"Expected at: {manager.key_file}")
    print("\nRun setup first:")
    print("  python -m robinhood.trading.setup_keys")
else:
    print(f"✓ Credentials file exists at: {manager.key_file}")
```

### Step 2: Set up credentials (first time only)
```bash
python -m robinhood.trading.setup_keys
```

This will:
- Load your API key and private key from your service key file
- Ask for an encryption method (password or file-based)
- Securely encrypt and save them
- **Remember this password!**

### Step 3: Use the correct password
```python
from robinhood.trading import RobinhoodClient, KeyManager

manager = KeyManager()

# Use the ACTUAL password you set during setup_keys.py
# NOT the string "your_password" from examples!
password = input("Enter your credentials password: ")

try:
    client = RobinhoodClient.from_key_manager(manager, password=password)
    print("✓ Successfully loaded credentials!")
except ValueError as e:
    print(f"❌ {e}")
    print("\nDid you use the correct password?")
```

---

## Error: `FileNotFoundError: Credentials file not found`

**Problem:**
```python
FileNotFoundError: Credentials file not found at ~/.robinhood/credentials.enc
Run setup_keys.py to create and encrypt your credentials first.
```

**Solution:**

You haven't set up your credentials yet. Run:
```bash
python -m robinhood.trading.setup_keys
```

---

## Error: `FileNotFoundError: Service key file not found`

**Problem:**
```python
FileNotFoundError: Service key file not found at .../robinhood.json
```

**Solution:**

The setup script looks for your Robinhood API credentials in a JSON file. You need to:

1. Set the `SERVICE_ROOT` environment variable:
   ```bash
   # Windows
   set SERVICE_ROOT=C:\path\to\your\keys
   
   # Linux/Mac
   export SERVICE_ROOT=/path/to/your/keys
   ```

2. Create `robinhood.json` in that directory:
   ```json
   {
     "api_key": "your-api-key-here",
     "private_key": "your-base64-private-key-here",
     "public_key": "your-public-key-here"
   }
   ```

3. Run setup again:
   ```bash
   python -m robinhood.trading.setup_keys
   ```

---

## Best Practice: Don't Hardcode Passwords

**Bad:**
```python
# DON'T DO THIS!
client = RobinhoodClient.from_key_manager(manager, password="my_password_123")
```

**Good:**
```python
import getpass

# Interactive (best for scripts)
password = getpass.getpass("Enter password: ")
client = RobinhoodClient.from_key_manager(manager, password=password)

# Or from environment variable (for automation)
import os
password = os.getenv("ROBINHOOD_PASSWORD")
if not password:
    raise ValueError("Set ROBINHOOD_PASSWORD environment variable")
client = RobinhoodClient.from_key_manager(manager, password=password)
```

---

## Quick Check Script

Save this as `check_setup.py`:

```python
#!/usr/bin/env python3
"""Check if Robinhood credentials are properly set up."""

from robinhood.trading import KeyManager, RobinhoodClient
import getpass
import sys

def main():
    print("Checking Robinhood setup...")
    print("=" * 70)
    
    # 1. Check if credentials file exists
    manager = KeyManager()
    print(f"\n1. Credentials file: {manager.key_file}")
    
    if not manager.key_file.exists():
        print("   ❌ NOT FOUND")
        print("\n   Run: python -m robinhood.trading.setup_keys")
        sys.exit(1)
    else:
        print("   ✓ EXISTS")
    
    # 2. Check if cipher key exists (for file-based encryption)
    print(f"\n2. Cipher key file: {manager.cipher_key_file}")
    
    if manager.cipher_key_file.exists():
        print("   ✓ EXISTS (using file-based encryption)")
        encryption_method = "file"
    else:
        print("   - Not found (using password-based encryption)")
        encryption_method = "password"
    
    # 3. Try to load credentials
    print(f"\n3. Testing credential loading ({encryption_method})...")
    
    try:
        if encryption_method == "file":
            cipher_key = manager.load_cipher_key()
            client = RobinhoodClient.from_key_manager(manager, cipher_key=cipher_key)
        else:
            password = getpass.getpass("   Enter your password: ")
            client = RobinhoodClient.from_key_manager(manager, password=password)
        
        print("   ✓ CREDENTIALS LOADED")
        
        # 4. Test API connection
        print("\n4. Testing Robinhood API connection...")
        account = client.get_account()
        
        if 'results' in account and len(account['results']) > 0:
            buying_power = account['results'][0].get('buying_power', 'N/A')
            print(f"   ✓ CONNECTED")
            print(f"   Buying Power: ${buying_power}")
        else:
            print("   ⚠️  Connected but unexpected response format")
        
    except ValueError as e:
        print(f"   ❌ FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("✓ All checks passed! You're ready to use the trading bot.")
    print("=" * 70)

if __name__ == "__main__":
    main()
```

Run it:
```bash
python check_setup.py
```

---

## Still Having Issues?

1. **Delete and recreate credentials:**
   ```bash
   rm ~/.robinhood/credentials.enc
   rm ~/.robinhood/cipher_key.key  # if exists
   python -m robinhood.trading.setup_keys
   ```

2. **Check file permissions:**
   ```bash
   ls -la ~/.robinhood/
   # Files should be readable by your user
   ```

3. **Verify your service key file:**
   ```bash
   cat $SERVICE_ROOT/robinhood.json
   # Should have valid JSON with api_key, private_key, public_key
   ```

4. **Check Python/package versions:**
   ```bash
   python --version  # Should be 3.8+
   pip show cryptography  # Should be installed
   ```
