"""Rest API interface for Robinhood Crypto Trading API"""
import base64
import datetime
from enum import Enum
import json
from typing import Any, Dict, Optional
import uuid
# import requests
from nacl.signing import SigningKey

from ._baseInterface import BaseInterface


def _get_keys():
    """ """
    SERVICE_KEY_FILE = "//THO_CLOUD/gavyn/service/robinhood.json"
    with open(SERVICE_KEY_FILE, 'r') as key_file:
        data = json.load(key_file)
    return data


KEYS = _get_keys()
API_KEY = KEYS.get("api")
BASE64_PRIVATE_KEY = KEYS.get("private")



__all__ = [
    "Robinhood"
]



class Robinhood(BaseInterface):
    """Adapted for interfacing with the Robinhood Crypto Trading API"""
    
    
    def __init__(self):
        super().__init__()
        if self._initialized:
            # If instance already initialized we'll return. Otherwise we'll
            # reinitialize all of our instance attrs.
            return
        
        # set the initialized flag to True
        self._initialized = True

        # Implement instance attributes after this line
        self.api_key = API_KEY
        private_key_seed = base64.b64decode(BASE64_PRIVATE_KEY)
        self.private_key = SigningKey(private_key_seed)

        self.method_mapping = {
            self.session.get: "GET",
            self.session.post: "POST"
        }

    @property
    def base_url(self):
        """Get the base URL for the blsever REST API"""
        return "https://trading.robinhood.com"

    def _get_authorization_header(self,
                                  method: str,
                                  path: str,
                                  body: dict,
                                  timestamp: int) -> Dict[str, str]:
        """
        
        
        """
        method = self.method_mapping.get(method)
        if not path.startswith("/"):
            path = f"/{path}"
        body = body if body else ""

        message_to_sign = f"{self.api_key}{timestamp}{path}{method}{body}"
        print("message_to_sign: ", message_to_sign)
        signed = self.private_key.sign(message_to_sign.encode("utf-8"))

        return {
            "x-api-key": self.api_key,
            "x-signature": base64.b64encode(signed.signature).decode("utf-8"),
            "x-timestamp": str(timestamp),
        }

    