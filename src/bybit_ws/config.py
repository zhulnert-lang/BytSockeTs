"""Configuration settings for the Bybit WebSocket FastAPI system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class MarketType(str, Enum):
    """Bybit market types for WebSocket endpoint selection."""

    SPOT = "spot"
    LINEAR = "linear"   # USDT perpetual
    INVERSE = "inverse"  # Inverse contracts


@dataclass
class WebSocketConfig:
    """WebSocket connection configuration."""

    ENDPOINTS: dict = field(default_factory=lambda: {
        MarketType.SPOT: "wss://stream.bybit.com/v5/public/spot",
        MarketType.LINEAR: "wss://stream.bybit.com/v5/public/linear",
        MarketType.INVERSE: "wss://stream.bybit.com/v5/public/inverse",
    })

    SYMBOLS: List[str] = field(default_factory=lambda: [
        "BTCUSDT",
        "ETHUSDT",
    ])

    ORDERBOOK_DEPTH: int = 50
    KLINE_INTERVAL: str = "1"

    RECONNECT_INTERVAL: float = 5.0
    MAX_RECONNECT_ATTEMPTS: int = 50
    PING_INTERVAL: float = 20.0
    PING_TIMEOUT: float = 10.0
    RECV_TIMEOUT: float = 60.0

    MAX_TRADES_PER_SYMBOL: int = 1000
    MAX_ORDERBOOK_SNAPSHOTS: int = 100
    MAX_TICKER_HISTORY: int = 500
    MAX_KLINE_HISTORY: int = 500


@dataclass
class AppConfig:
    """Application-level configuration."""

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    MARKET_TYPE: MarketType = MarketType.LINEAR

    SUBSCRIBE_TRADES: bool = True
    SUBSCRIBE_ORDERBOOK: bool = True
    SUBSCRIBE_TICKERS: bool = True
    SUBSCRIBE_KLINES: bool = True

    VWAP_WINDOW: int = 100
    ROLLING_STATS_WINDOW: int = 200

    CORS_ORIGINS: list = field(default_factory=lambda: ["*"])


ws_config = WebSocketConfig()
app_config = AppConfig()
