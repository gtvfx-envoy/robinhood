"""
Generate Ed25519 key pair for Robinhood API.

This script generates a new Ed25519 key pair for use with the Robinhood Crypto API.
You'll need to submit the public key when creating API credentials on Robinhood.
"""
import nacl.signing
import base64


def generate_keypair():
    """Generate Ed25519 key pair and print in Base64 format."""
    
    print("="*70)
    print("Robinhood API Key Pair Generator")
    print("="*70)
    print()
    
    # Generate keypair
    print("Generating Ed25519 key pair...")
    private_key = nacl.signing.SigningKey.generate()
    public_key = private_key.verify_key
    
    # Convert to base64
    private_key_base64 = base64.b64encode(private_key.encode()).decode()
    public_key_base64 = base64.b64encode(public_key.encode()).decode()
    
    print("✓ Key pair generated successfully!")
    print()
    print("="*70)
    print("PUBLIC KEY (submit this to Robinhood):")
    print("="*70)
    print(public_key_base64)
    print()
    print("="*70)
    print("PRIVATE KEY (keep this SECRET and secure!):")
    print("="*70)
    print(private_key_base64)
    print()
    print("="*70)
    print("IMPORTANT:")
    print("="*70)
    print("1. Copy the PUBLIC KEY above")
    print("2. Go to: https://robinhood.com/account/crypto")
    print("3. Create a new API credential using the public key")
    print("4. Save the API key you receive")
    print("5. Run 'python -m robinhood_trading.setup_keys' to encrypt and store your keys")
    print()
    print("⚠️  NEVER share your PRIVATE KEY with anyone!")
    print("⚠️  Robinhood will NEVER ask you for your private key!")
    print()


if __name__ == "__main__":
    generate_keypair()
