"""Singleton Abstract Base Class"""
from abc import ABC


__all__ = [
    "ABCSingleton"
]


class ABCSingleton(ABC):
    """An Abstract Base Class that will be implemented as a Singleton object
    
    
    ## Example:
    ```python
    from t2.abstractclasses import ABCSingleton
    
    class BaseInterface(ABCSingleton):
        def __init__(self):
            super().__init__()
            
            if self._initialized:
                # If instance already initialized we'll return. Otherwise we'll
                # reinitialize all of our instance attrs.
                return
            
            # set the initialized flag to True
            self._initialized = True

            # Implement instance attributes after this line
    ```
    
    
    Args:
        reinit (bool): Force the value of the _initialized attribute. Can force
            new instantiations of the Singleton to fully run the __init__ method.
    
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
            cls._initialized = False
        return cls._instance
    