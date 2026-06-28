# System Architecture

## Overview

bybit-ws follows a layered architecture with clear separation of concerns:

```
Client Apps (REST + WebSocket)
        |
   FastAPI App (app.py)
   /    |    \
  /     |     \
Manager  Store  Analytics
  |       |       |
  v       v       v
Bybit   Memory   NumPy
  WS    Buffers  Compute
```

## Components

### 1. WebSocket Manager (`manager.py`)

Manages the persistent connection to Bybit V5 public WebSocket API.

**Responsibilities:**
- Connection establishment and automatic reconnection
- Heartbeat/ping-pong keepalive
- Topic-based message routing
- Subscription management (subscribe/unsubscribe)
- Orderbook delta application to snapshots

**Reconnection Strategy:**
- Exponential backoff: 5s, 10s, 20s, 40s... capped at 60s
- Maximum 50 reconnection attempts (configurable)
- Automatic topic re-subscription on reconnect

### 2. Data Store (`store.py`)

Thread-safe in-memory storage with bounded buffers per symbol.

**Data Types:**
| Type | Buffer Size | Description |
|------|-------------|-------------|
| Trades | 1,000 per symbol | Individual trade records |
| Orderbook Snapshots | 1 (latest only) | Full orderbook state |
| Orderbook Deltas | 100 per symbol | Incremental updates |
| Tickers | 500 per symbol | 24hr ticker history |
| Klines | 500 per symbol | Candlestick data |

**Thread Safety:**
All read/write operations use `asyncio.Lock` to prevent race conditions.

### 3. Analytics Engine (`analytics.py`)

Computes real-time analytics from stored data.

**Available Analytics:**

| Analytics | Method | Description |
|-----------|--------|-------------|
| VWAP | `calculate_vwap()` | Volume-Weighted Average Price |
| Rolling Stats | `calculate_rolling_stats()` | Mean, std, min, max over window |
| Spread | `analyze_spread()` | Bid-ask spread (absolute + basis points) |
| Summary | `get_symbol_summary()` | Comprehensive per-symbol summary |

### 4. FastAPI App (`app.py`)

Exposes 19 REST endpoints + WebSocket streaming.

**Endpoint Categories:**
- **System** (6): Health, config, status, topics, stats, root
- **Market Data** (7): Symbols, trades, orderbook, deltas, ticker, history, klines
- **Analysis** (5): VWAP, rolling stats, spread, summary (single/all)
- **Subscriptions** (2): Subscribe (POST), unsubscribe (DELETE)
- **Streaming** (1): WebSocket `/ws/stream`

### 5. Models (`models.py`)

Pydantic v2 models for data validation.

**Raw Data Models:**
- `TradeData` - Individual trade record
- `OrderBookSnapshot` - Full orderbook state
- `OrderBookDelta` - Incremental orderbook update
- `TickerData` - 24hr ticker with all Bybit fields
- `KlineData` - Candlestick/OHLCV data

**Analytics Models:**
- `VWAPResult` - VWAP calculation result
- `RollingStats` - Rolling statistics output
- `SpreadAnalysis` - Spread analysis result
- `SymbolSummary` - Comprehensive symbol summary

**System Models:**
- `ConnectionStatus` - WebSocket connection state
- `SubscriptionRequest` - Subscribe/unsubscribe request
- `SystemStats` - System-wide statistics

### 6. Configuration (`config.py`)

Centralized configuration via dataclasses.

**Config Objects:**
- `AppConfig` - Server, market type, topic toggles, analysis windows
- `WebSocketConfig` - Endpoints, symbols, depth, intervals, buffer sizes

**Market Types:**
| Type | Endpoint | Use Case |
|------|----------|----------|
| `SPOT` | `wss://stream.bybit.com/v5/public/spot` | Spot trading |
| `LINEAR` | `wss://stream.bybit.com/v5/public/linear` | USDT perpetual |
| `INVERSE` | `wss://stream.bybit.com/v5/public/inverse` | Inverse contracts |

## Data Flow

```
Bybit WebSocket
      |
      v
  Manager._handle_raw_message()
      |
      +---> _handle_trade_message()    ---> store.add_trades()
      +---> _handle_orderbook_message() ---> store.update_orderbook_snapshot()
      |                                   store.update_orderbook_delta()
      +---> _handle_ticker_message()   ---> store.update_ticker()
      +---> _handle_kline_message()    ---> store.add_kline()
      
  API Request
      |
      v
  Endpoint ---> DataProcessor ---> DataStore ---> Response
```

## Extension Points

1. **Custom Message Handlers**: Override `manager.on_message` callback
2. **Custom Analytics**: Add methods to `DataProcessor`
3. **Custom Endpoints**: Add routes to the FastAPI app
4. **Custom Storage**: Replace `DataStore` with your backend
