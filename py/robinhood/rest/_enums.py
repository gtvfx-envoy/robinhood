""""""
from enum import Enum, StrEnum, auto


__all__ = [
    "EstimateSides",
    "OrderSides",
    "OrderState",
    "OrderType",
    "TimeInForce"
]



class EstimateSides(StrEnum):
    BID = auto()
    ASK = auto()
    BOTH = auto()


class OrderSides(StrEnum):
    BUY = auto()
    SELL = auto()


class OrderState(StrEnum):
    OPEN = auto()
    CANCELED = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    FAILED = auto()


class OrderType(StrEnum):
    LIMIT = auto()
    MARKET = auto()
    STOP_LIMIT = auto()
    STOP_LOSS = auto()


class TimeInForce(StrEnum):
    GTC = auto() # The order remains open until it's filled or the user cancels it.
    GFD = auto() # The order remains open until the end of the day or when the user cancels it.
    GFW = auto() # The order remains open until the end of the week or when the user cancels it.
    GFM = auto() # The order remains open until the end of the month or when the user cancels it.
