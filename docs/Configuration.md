# Configuration

All configuration is centralized in `src/bybit_ws/config.py` via two dataclass singletons.

## AppConfig

Application-level settings.

```python
from bybit_ws import app_config, MarketType

# Server
app_config.HOST = "0.0.0.0"       # Bind address
app_config.PORT = 8000             # Port number
app_config.DEBUG = False           # Enable reload mode
app_config.LOG_LEVEL = "INFO"      # DEBUG | INFO | WARNING | ERROR

# Market type
app_config.MARKET_TYPE = MarketType.LINEAR  # SPOT | LINEAR | INVERSE

# Topic toggles
app_config.SUBSCRIBE_TRADES = True
app_config.SUBSCRIBE_ORDERBOOK = True
app_config.SUBSCRIBE_TICKERS = True
app_config.SUBSCRIBE_KLINES = True

# Analysis windows
app_config.VWAP_WINDOW = 100           # Trades for VWAP calculation
app_config.ROLLING_STATS_WINDOW = 200  # Trades for rolling stats

# CORS
app_config.CORS_ORIGINS = ["*"]  # Allowed origins
```

## WebSocketConfig

WebSocket connection and buffer settings.

```python
from bybit_ws import ws_config

# Symbols to track
ws_config.SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# Orderbook depth: 1, 50, or 200
ws_config.ORDERBOOK_DEPTH = 50

# Kline interval: "1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "W", "M"
ws_config.KLINE_INTERVAL = "1"

# Connection settings
ws_config.RECONNECT_INTERVAL = 5.0     # Base interval (seconds)
ws_config.MAX_RECONNECT_ATTEMPTS = 50  # 0 = infinite
ws_config.PING_INTERVAL = 20.0         # Heartbeat interval (seconds)
ws_config.PING_TIMEOUT = 10.0          # Pong timeout (seconds)
ws_config.RECV_TIMEOUT = 60.0          # No-data timeout (seconds)

# Buffer sizes (per symbol)
ws_config.MAX_TRADES_PER_SYMBOL = 1000
ws_config.MAX_ORDERBOOK_SNAPSHOTS = 100
ws_config.MAX_TICKER_HISTORY = 500
ws_config.MAX_KLINE_HISTORY = 500
```

## Market Types

| Type | Value | WebSocket Endpoint | Use Case |
|------|-------|-------------------|----------|
| `MarketType.SPOT` | `"spot"` | `wss://stream.bybit.com/v5/public/spot` | Spot trading pairs |
| `MarketType.LINEAR` | `"linear"` | `wss://stream.bybit.com/v5/public/linear` | USDT perpetual contracts |
| `MarketType.INVERSE` | `"inverse"` | `wss://stream.bybit.com/v5/public/inverse` | Inverse (coin-margined) contracts |

## WebSocket Topics

Bybit V5 public topics subscribed based on configuration:

| Topic Pattern | Config Toggle | Example |
|---------------|---------------|---------|
| `publicTrade.{symbol}` | `SUBSCRIBE_TRADES` | `publicTrade.BTCUSDT` |
| `orderbook.{depth}.{symbol}` | `SUBSCRIBE_ORDERBOOK` | `orderbook.50.BTCUSDT` |
| `tickers.{symbol}` | `SUBSCRIBE_TICKERS` | `tickers.BTCUSDT` |
| `kline.{interval}.{symbol}` | `SUBSCRIBE_KLINES` | `kline.1.BTCUSDT` |

## Runtime Configuration

Configuration can be modified before creating the manager:

```python
from bybit_ws import app_config, ws_config, BybitWebSocketManager, DataStore

# Modify config
app_config.MARKET_TYPE = MarketType.SPOT
ws_config.SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]
ws_config.ORDERBOOK_DEPTH = 200

# Create manager (reads config at init time)
store = DataStore()
manager = BybitWebSocketManager(store=store)
```

> **Note:** Changing `ws_config.SYMBOLS` after the manager is created does NOT automatically update subscriptions. Use `manager.subscribe()` for runtime changes.
