import functools


def logFunc(func=None, *, force=False):
    """Simple logging decorator used by ApiClient."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if force:
                print(f"Calling {f.__name__}")
            return f(*args, **kwargs)
        return wrapper
    if func is None:
        return decorator
    else:
        return decorator(func)
