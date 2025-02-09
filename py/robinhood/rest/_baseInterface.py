"""Abstract base interface for a REST API"""
from abc import abstractmethod
import base64
from datetime import datetime, timezone
import json
import requests
from typing import Any, Dict, Optional
from urllib.parse import urljoin

from ._abc_singleton import ABCSingleton
from ._captureException import CaptureException


__all__ = [
    "BaseInterface",
    "RestException"
]



class RestException(Exception):
    """Base exception for REST API"""
    ...
    

class BaseInterface(ABCSingleton):
    """Object for interfacing with a REST API
    
    Args:
        timeout (int): The timeout provided to api requests
    
    """
    # Using requests.Session reduces API overhead by reusing the same TCP 
    # connection and reduces the call time by roughly 50%
    session = requests.Session()
    timeout = 10
    
    @property
    @abstractmethod
    def base_url(self):
        """Get the base URL for the blsever REST API"""
        raise NotImplementedError
        
    @property
    def auth(self):
        """Get the auth attribute of self.session"""
        return self.session.auth
    
    @auth.setter
    def auth(self, value):
        self.session.auth = value

    @staticmethod
    def _get_current_timestamp() -> int:
        return int(datetime.now(tz=timezone.utc).timestamp())
    
    @CaptureException
    def _request(self, method, endpoint: str, data=None) -> Dict[str, Any]:
        """Perform a request to the REST API
        
        Args:
            method(str): The method to use for the request.
            endpoint(str): The endpoint to request.
            data(dict): The data to send with the request.
            
        Returns:
            Union[dict, list]: Returns a JSON object. Can be a list[dict] or dict.
        
        """
        if data is None:
            data = {}

        timestamp = self._get_current_timestamp()
        headers = self._get_authorization_header(method, endpoint, data, timestamp)
        
        url = urljoin(self.base_url, endpoint)
        print(f"Requesting {url} with headers: {headers}")
        print(f"Data: {data}")
        if method == self.session.get:
            response = method(url, headers=headers, timeout=self.timeout)
        elif method == self.session.post:
            response = method(url, headers=headers, json=data, timeout=self.timeout)
        
        if not response:
            raise RestException(f"{response.status_code}: {response.text}")
        return response.json()
    
    @abstractmethod
    def _get_authorization_header(
            self, method: str, path: str, body: str, timestamp: int
    ) -> Dict[str, str]:
        raise NotImplementedError

    def get(self, endpoint, data=None):
        """Perform a GET request to the REST API
        
        Args:
            endpoint(str): The endpoint to request.
            data(dict): The data to send with the request.
            
        Returns:
            dict: response for the function requested.
        
        """
        return self._request(self.session.get, endpoint, data)

    def post(self, endpoint, data=None):
        """Perform a POST request to the REST API
        
        Args:
            endpoint(str): The endpoint to send the request to.
            data(dict): The data to send with the request.
            
        Returns:
            dict: The response from the request.
        
        """
        return self._request(self.session.post, endpoint, data)

    def put(self, endpoint, data=None):
        """Perform a PUT request to the REST API
        
        Args:
            endpoint(str): The endpoint to send the request to.
            data(dict): The data to send with the request.
            
        Returns:
            dict: The response from the request.
            
        """
        return self._request(self.session.put, endpoint, data)
    
    def delete(self, endpoint: str) -> dict:
        """Perform a DELETE request to the REST API
        
        Args:
            endpoint(str): The endpoint to send the request to.
            
        Returns:
            dict: The response from the request.
        
        """
        return self._request(self.session.delete, endpoint)
