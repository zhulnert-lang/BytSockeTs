"""bybit-ws: Real-time Bybit market data ingestion and analytics.

Usage as a library::

    from bybit_ws import DataStore, DataProcessor, BybitWebSocketManager, MarketType

    store = DataStore()
    processor = DataProcessor(store)
    manager = BybitWebSocketManager(store=store, market_type=MarketType.LINEAR)

Or mount the FastAPI app::

    from bybit_ws.app import app
"""

from __future__ import annotations

from .analytics import DataProcessor
from .config import AppConfig, MarketType, WebSocketConfig, app_config, ws_config
from .exceptions import (
    BybitConnectionError,
    BybitWSError,
    ConfigurationError,
    DataNotFoundError,
    SubscriptionError,
)
from .manager import BybitWebSocketManager
from .models import (
    ConnectionStatus,
    KlineData,
    OrderBookDelta,
    OrderBookLevel,
    OrderBookSnapshot,
    RollingStats,
    SpreadAnalysis,
    SubscriptionRequest,
    SymbolSummary,
    SystemStats,
    TickerData,
    TradeData,
    TradeMessage,
    VWAPResult,
)
from .store import DataStore

__version__ = "1.0.0"

__all__ = [
    # Config
    "AppConfig",
    "MarketType",
    "WebSocketConfig",
    "app_config",
    "ws_config",
    # Models — raw
    "TradeData",
    "TradeMessage",
    "OrderBookLevel",
    "OrderBookSnapshot",
    "OrderBookDelta",
    "TickerData",
    "KlineData",
    # Models — analytics
    "VWAPResult",
    "RollingStats",
    "SpreadAnalysis",
    "SymbolSummary",
    # Models — system
    "ConnectionStatus",
    "SubscriptionRequest",
    "SystemStats",
    # Core components
    "DataStore",
    "DataProcessor",
    "BybitWebSocketManager",
    # Exceptions
    "BybitWSError",
    "BybitConnectionError",
    "DataNotFoundError",
    "SubscriptionError",
    "ConfigurationError",
]
