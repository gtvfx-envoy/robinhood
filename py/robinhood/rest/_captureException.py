"""Decorator for capturing exceptions from the requests module"""
import requests

from logging import log


__all__ = [
    "CaptureException"
]



class CaptureException:
    def __init__(self, method):
        self.method = method

    def __call__(self, instance, *args, **kwargs):
        try:
            return self.method(instance, *args, **kwargs)
        except requests.exceptions.ConnectionError as e:
            log.exception(f"API request failed to connect to server:\n{e}")
        except requests.exceptions.Timeout as e:
            log.exception(f"API request timed out:\n{e}")
        except requests.exceptions.JSONDecodeError as e:
            # Using log.exception or log.warn puts aggressive text in the output
            # that will disconcert users. An error here is likely a malformed
            # API endpoint. This should be conveyed to the owner of the API, but
            # our tools can safely expect to get an empty dict in this case.
            log.info(f"API request failed to decode JSON: {e}")
            # If we get a bad JSON response we'll return an empty dict so that
            # our interface can reasonably assume to have a valid JSON object.
            return {}
        except requests.exceptions.RequestException as e:
            log.exception(f"Request exception occurred:\n{e}")
            
    def __get__(self, instance, owner):
        def wrapper(*args, **kwargs):
            return self.__call__(instance, *args, **kwargs)
        return wrapper
    