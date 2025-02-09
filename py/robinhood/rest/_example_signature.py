import nacl.signing
import base64
import time

# Replace these with your base64-encoded keys
private_key_base64 = "xQnTJVeQLmw1/Mg2YimEViSpw/SdJcgNXZ5kQkAXNPU="
public_key_base64 = "jPItx4TLjcnSUnmnXQQyAKL4eJj3+oWNNMmmm2vATqk="

api_key = "rh-api-6148effc-c0b1-486c-8940-a1d099456be6"

# Get the current Unix timestamp in seconds
# You can get the current_timestamp with the following code:
# current_timestamp = int(time.time())
# This value is hardcoded for demonstration purposes to match the example in the documentation
current_timestamp = "1698708981"

path = f"/api/v1/crypto/trading/orders/"

method = "POST"

body = {
    "client_order_id": "131de903-5a9c-4260-abc1-28d562a5dcf0",
    "side": "buy",
    "symbol": "BTC-USD",
    "type": "market",
    "market_order_config": {
        "asset_quantity": "0.1"
    },
}

# Convert base64 strings to seed (for private key) and bytes (for public key)
private_key_seed = base64.b64decode(private_key_base64)
public_key_bytes = base64.b64decode(public_key_base64)

# Create private key (from seed) and public key (from bytes)
private_key = nacl.signing.SigningKey(private_key_seed)
public_key = nacl.signing.VerifyKey(public_key_bytes)

# Create the message to sign
message = f"{api_key}{current_timestamp}{path}{method}{body}"

# Sign the message
signed = private_key.sign(message.encode("utf-8"))

base64_signature = base64.b64encode(signed.signature).decode("utf-8")
print(base64_signature)

# Verify the signature
public_key.verify(signed.message, signed.signature)