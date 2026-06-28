"""Custom exception hierarchy for bybit-ws."""


class BybitWSError(Exception):
    """Base exception for all bybit-ws errors."""


class BybitConnectionError(BybitWSError):
    """Raised when the WebSocket connection fails or is lost."""


class DataNotFoundError(BybitWSError):
    """Raised when requested market data is not available."""


class SubscriptionError(BybitWSError):
    """Raised when a subscription or unsubscription request fails."""


class ConfigurationError(BybitWSError):
    """Raised when the configuration is invalid or incomplete."""
