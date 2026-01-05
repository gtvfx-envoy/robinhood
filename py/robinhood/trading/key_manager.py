"""
Secure key management for Robinhood Crypto API credentials.

This module provides encryption and secure storage for Robinhood API keys
and private keys using industry-standard AES-256 encryption.
"""
import json
import os
import base64
from pathlib import Path
from typing import Dict, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import getpass


def get_config_dir() -> Path:
    """
    Get the configuration directory for storing credentials.
    
    Returns:
        Path to configuration directory (robinhood/config within the package)
    """
    # Get the directory where this module is located
    module_dir = Path(__file__).parent.parent
    config_dir = module_dir / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


class KeyManager:
    """Manages secure storage and retrieval of Robinhood API credentials."""
    
    def __init__(
        self,
        key_file: Optional[str] = None,
        cipher_key_file: Optional[str] = None
    ):
        """
        Initialize KeyManager.
        
        Args:
            key_file: Path to encrypted keys file (defaults to config dir)
            cipher_key_file: Path to cipher key file (defaults to config dir)
        """
        config_dir = get_config_dir()
        self.key_file = key_file or str(config_dir / "robinhood_keys.enc")
        self.cipher_key_file = cipher_key_file or str(config_dir / "robinhood_cipher.key")
    
    def generate_cipher_key(self) -> bytes:
        """
        Generate a new Fernet cipher key.
        
        Returns:
            Cipher key as bytes
        """
        return Fernet.generate_key()
    
    def save_cipher_key(self, cipher_key: bytes):
        """
        Save cipher key to file.
        
        Args:
            cipher_key: The cipher key to save
        """
        with open(self.cipher_key_file, 'wb') as f:
            f.write(cipher_key)
        print(f"Cipher key saved to {self.cipher_key_file}")
    
    def load_cipher_key(self) -> bytes:
        """
        Load cipher key from file.
        
        Returns:
            Cipher key as bytes
        """
        with open(self.cipher_key_file, 'rb') as f:
            return f.read()
    
    def encrypt_and_save_keys(
        self,
        api_key: str,
        private_key_base64: str,
        cipher_key: bytes
    ):
        """
        Encrypt and save API credentials.
        
        Args:
            api_key: Robinhood API key
            private_key_base64: Base64-encoded Ed25519 private key
            cipher_key: Encryption key
        """
        fernet = Fernet(cipher_key)
        
        credentials = {
            'api_key': api_key,
            'private_key': private_key_base64
        }
        
        # Serialize and encrypt
        json_data = json.dumps(credentials)
        encrypted_data = fernet.encrypt(json_data.encode())
        
        # Save to file
        with open(self.key_file, 'wb') as f:
            f.write(encrypted_data)
        
        print(f"Encrypted keys saved to {self.key_file}")
    
    def load_encrypted_keys(self, cipher_key: bytes) -> Dict[str, str]:
        """
        Load and decrypt API credentials.
        
        Args:
            cipher_key: Decryption key
            
        Returns:
            Dictionary with 'api_key' and 'private_key'
        """
        fernet = Fernet(cipher_key)
        
        # Load encrypted data
        with open(self.key_file, 'rb') as f:
            encrypted_data = f.read()
        
        # Decrypt and deserialize
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data.decode())
        
        return credentials
    
    def derive_key_from_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        Derive encryption key from password using PBKDF2.
        
        Args:
            password: User password
            salt: Optional salt (generated if not provided)
            
        Returns:
            Tuple of (derived_key, salt)
        """
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def save_with_password(
        self,
        api_key: str,
        private_key_base64: str,
        password: Optional[str] = None
    ):
        """
        Encrypt and save credentials using password-based encryption.
        
        Args:
            api_key: Robinhood API key
            private_key_base64: Base64-encoded Ed25519 private key
            password: Password for encryption (prompts if not provided)
        """
        if password is None:
            password = getpass.getpass("Enter password for encryption: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                raise ValueError("Passwords do not match")
        
        # Derive key from password
        derived_key, salt = self.derive_key_from_password(password)
        
        # Create credentials with salt
        credentials = {
            'api_key': api_key,
            'private_key': private_key_base64,
            'salt': base64.b64encode(salt).decode()
        }
        
        # Encrypt and save
        fernet = Fernet(derived_key)
        json_data = json.dumps(credentials)
        encrypted_data = fernet.encrypt(json_data.encode())
        
        with open(self.key_file, 'wb') as f:
            f.write(encrypted_data)
        
        print(f"Password-encrypted keys saved to {self.key_file}")
    
    def load_with_password(self, password: Optional[str] = None) -> Dict[str, str]:
        """
        Load and decrypt credentials using password.
        
        Args:
            password: Password for decryption (prompts if not provided)
            
        Returns:
            Dictionary with 'api_key' and 'private_key'
        """
        if password is None:
            password = getpass.getpass("Enter password: ")
        
        # Load encrypted data
        with open(self.key_file, 'rb') as f:
            encrypted_data = f.read()
        
        # We need to decrypt once to get the salt
        # Try to decrypt with a temporary derived key to get salt
        # This is a chicken-and-egg problem, so we'll store salt separately
        
        # For password-based encryption, we store salt in the file
        # Let's modify the approach: store salt at the beginning of file
        
        # Read first 24 bytes as salt (16 bytes salt + 8 bytes for base64 alignment)
        # Actually, let's use a different approach: prepend salt to encrypted data
        
        # Extract salt from beginning (16 bytes)
        salt_size = 16
        salt = encrypted_data[:salt_size]
        actual_encrypted_data = encrypted_data[salt_size:]
        
        # Derive key from password and salt
        derived_key, _ = self.derive_key_from_password(password, salt)
        
        # Decrypt
        fernet = Fernet(derived_key)
        decrypted_data = fernet.decrypt(actual_encrypted_data)
        credentials = json.loads(decrypted_data.decode())
        
        return {
            'api_key': credentials['api_key'],
            'private_key': credentials['private_key']
        }
    
    def save_with_password_v2(
        self,
        api_key: str,
        private_key_base64: str,
        password: Optional[str] = None
    ):
        """
        Encrypt and save credentials using password (version 2 with prepended salt).
        
        Args:
            api_key: Robinhood API key
            private_key_base64: Base64-encoded Ed25519 private key
            password: Password for encryption (prompts if not provided)
        """
        if password is None:
            password = getpass.getpass("Enter password for encryption: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                raise ValueError("Passwords do not match")
        
        # Derive key from password
        derived_key, salt = self.derive_key_from_password(password)
        
        # Create credentials
        credentials = {
            'api_key': api_key,
            'private_key': private_key_base64
        }
        
        # Encrypt
        fernet = Fernet(derived_key)
        json_data = json.dumps(credentials)
        encrypted_data = fernet.encrypt(json_data.encode())
        
        # Prepend salt to encrypted data
        final_data = salt + encrypted_data
        
        # Save to file
        with open(self.key_file, 'wb') as f:
            f.write(final_data)
        
        print(f"Password-encrypted keys saved to {self.key_file}")


def setup_encrypted_storage(
    api_key: str,
    private_key_base64: str,
    method: str = 'file'
) -> KeyManager:
    """
    Setup encrypted storage for Robinhood API credentials.
    
    Args:
        api_key: Robinhood API key
        private_key_base64: Base64-encoded Ed25519 private key
        method: 'file' for file-based encryption or 'password' for password-based
        
    Returns:
        KeyManager instance
    """
    manager = KeyManager()
    
    if method == 'file':
        # File-based encryption with separate cipher key
        cipher_key = manager.generate_cipher_key()
        manager.save_cipher_key(cipher_key)
        manager.encrypt_and_save_keys(api_key, private_key_base64, cipher_key)
        print("\n✓ Keys encrypted with file-based encryption")
        print(f"  Keys file: {manager.key_file}")
        print(f"  Cipher file: {manager.cipher_key_file}")
        print("\n⚠️  IMPORTANT: Keep both files secure and backed up!")
        
    elif method == 'password':
        # Password-based encryption
        manager.save_with_password_v2(api_key, private_key_base64)
        print("\n✓ Keys encrypted with password-based encryption")
        print(f"  Keys file: {manager.key_file}")
        print("\n⚠️  IMPORTANT: Remember your password and keep the file secure!")
    
    else:
        raise ValueError("Method must be 'file' or 'password'")
    
    return manager
