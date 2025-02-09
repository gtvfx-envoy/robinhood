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
    DAY = auto() # only valid for the current trading day
    GTC = auto() # remains active until filled or manually cancelled
    IOC = auto() # fills as much as possible immediately, cancelling the rest
    FOK = auto() # must be filled entirely immediately or the entire order is cancelled
