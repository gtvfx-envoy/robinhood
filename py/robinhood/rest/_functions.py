"""Helper functions for the Robinhood API."""


from ._interface import CryptoAPITrading

rh = CryptoAPITrading()




def get_crypto_holdings():
    """Get the current holdings of the authenticated user."""
    return rh.get_holdings().get("results")

