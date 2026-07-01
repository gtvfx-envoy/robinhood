import base64

import nacl.signing

# Demo-only key material generated at runtime. Do not hard-code live keys.
private_key = nacl.signing.SigningKey.generate()
public_key = private_key.verify_key

api_key = "rh-api-demo"

# Get the current Unix timestamp in seconds
# You can get the current_timestamp with the following code:
# current_timestamp = int(time.time())
# This value is hardcoded for demonstration purposes to match the example in the documentation
current_timestamp = "1698708981"

path = "/api/v1/crypto/trading/orders/"

method = "POST"

body = {
    "client_order_id": "131de903-5a9c-4260-abc1-28d562a5dcf0",
    "side": "buy",
    "symbol": "BTC-USD",
    "type": "market",
    "market_order_config": {"asset_quantity": "0.1"},
}

# Create the message to sign
message = f"{api_key}{current_timestamp}{path}{method}{body}"

# Sign the message
signed = private_key.sign(message.encode("utf-8"))

base64_signature = base64.b64encode(signed.signature).decode("utf-8")
print(base64_signature)

# Verify the signature
public_key.verify(signed.message, signed.signature)
