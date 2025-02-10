"""Logging decorators"""
import functools
import inspect
import os



__all__ = [
    "logFunc",
    "makeRelativePath"
]


def makeRelativePath(path: str, relative_token: str="") -> str:
    """Concatenate a path relative to the relative_token arg.
    
    Args:
        path (str): Any system path
        relative_token (str): A folder name within path
    
    Returns:
        str
    
    """
    rel = "...\\"
    path = os.path.normpath(path)
    tokens = path.split(os.sep)
    
    if relative_token == "":
        tokens[0] = "..."
        return os.path.join(*tokens)
    
    if relative_token in tokens:
        token_index = tokens.index(relative_token)
    else:
        token_index = 0
        
    rel_tokens = tokens[token_index:]
    return os.path.join(rel, *rel_tokens)



def logFunc(force=False):
    """Logs the call to the wrapped func with all args and kwargs"""
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args, **kwargs):
            if force or os.getenv("LOG_DEBUG").lower() in ("1", "true"):
                from_module = inspect.stack()[1][1]
                
                if from_module == '<stdin>':
                    # This means we're in a python REPL
                    module_path = from_module
                else:
                    module_path = makeRelativePath(from_module, relative_token="repo")
                
                msg = f"call: {module_path} | {func.__name__}("
                if args:
                    msg = f"{msg}{str(args)[1:-2]}"
                if kwargs:
                    if args:
                        # If we had args add a ',' before kwargs
                        msg += ", "
                    msg = f"{msg}{', '.join([f'{k}={v}' for k,v in kwargs.items()])}"
                msg += ")"
                print(msg)
            return func(*args, **kwargs)
        return _wrapper
    return _decorator
