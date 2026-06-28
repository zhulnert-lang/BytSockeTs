# REST API Reference

Complete reference for all 19 REST endpoints.

Base URL: `http://localhost:8000`

Interactive documentation: http://localhost:8000/docs

---

## System Endpoints

### `GET /`

API information and endpoint listing.

**Response:**
```json
{
  "service": "Bybit WebSocket FastAPI System",
  "version": "1.0.0",
  "docs": "/docs",
  "endpoints": { ... }
}
```

---

### `GET /health`

Connection health check with server time.

**Response:**
```json
{
  "status": "healthy",
  "connected": true,
  "market_type": "linear",
  "symbols_tracked": 2,
  "reconnect_attempts": 0,
  "server_time": "2026-01-15T10:30:00+00:00",
  "started_at": "2026-01-15T08:00:00+00:00"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"healthy"` or `"degraded"` |
| `connected` | boolean | WebSocket connection state |
| `market_type` | string | `"spot"`, `"linear"`, or `"inverse"` |
| `symbols_tracked` | integer | Number of active symbols |
| `server_time` | string | Current server time (ISO 8601) |
| `started_at` | string | Server start time (ISO 8601) |

---

### `GET /config`

Current system configuration.

**Response:**
```json
{
  "market_type": "linear",
  "market_type_name": "LINEAR",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "orderbook_depth": 50,
  "kline_interval": "1",
  "subscribe_trades": true,
  "subscribe_orderbook": true,
  "subscribe_tickers": true,
  "subscribe_klines": true,
  "vwap_window": 100,
  "rolling_stats_window": 200,
  "max_reconnect_attempts": 50,
  "ping_interval": 20.0
}
```

---

### `GET /status`

Detailed WebSocket connection status.

**Response:** `ConnectionStatus` model
```json
{
  "market_type": "linear",
  "is_connected": true,
  "reconnect_attempts": 0,
  "last_ping": "2026-01-15T10:30:00+00:00",
  "last_message": "2026-01-15T10:30:01+00:00",
  "topics_subscribed": [
    "publicTrade.BTCUSDT",
    "orderbook.50.BTCUSDT",
    "tickers.BTCUSDT",
    "kline.1.BTCUSDT"
  ],
  "errors": []
}
```

---

### `GET /topics`

List all currently subscribed WebSocket topics.

**Response:**
```json
{
  "connected": true,
  "count": 8,
  "topics": [
    "kline.1.BTCUSDT",
    "kline.1.ETHUSDT",
    "orderbook.50.BTCUSDT",
    "orderbook.50.ETHUSDT",
    "publicTrade.BTCUSDT",
    "publicTrade.ETHUSDT",
    "tickers.BTCUSDT",
    "tickers.ETHUSDT"
  ]
}
```

---

### `GET /stats`

System-wide statistics.

**Response:** `SystemStats` model
```json
{
  "total_symbols_tracked": 2,
  "total_messages_received": 15234,
  "total_trades_processed": 8456,
  "total_errors": 0,
  "uptime_seconds": 9000.5,
  "connections": [ ... ]
}
```

---

## Market Data Endpoints

### `GET /symbols`

List all symbols currently being tracked.

**Response:**
```json
{
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "count": 2
}
```

---

### `GET /trades/{symbol}`

Get recent trades for a symbol.

**Parameters:**
| Name | In | Type | Default | Description |
|------|-----|------|---------|-------------|
| `symbol` | path | string | — | Trading pair (e.g., `BTCUSDT`) |
| `limit` | query | integer | `100` | Max results (1-1000) |

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "count": 100,
  "trades": [
    {
      "id": "trade-id-string",
      "price": 42000.50,
      "quantity": 0.001,
      "side": "Buy",
      "timestamp": 1705312200000,
      "timestamp_iso": "2026-01-15T10:30:00",
      "block_trade": false
    }
  ]
}
```

**Errors:** `404` — No trades found for symbol

---

### `GET /orderbook/{symbol}`

Get the latest orderbook snapshot.

**Parameters:**
| Name | In | Type | Default | Description |
|------|-----|------|---------|-------------|
| `symbol` | path | string | — | Trading pair |
| `depth` | query | integer | `50` | Levels to return (1-200) |

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "bids": [{"price": 42000.0, "size": 1.5}, ...],
  "asks": [{"price": 42001.0, "size": 0.8}, ...],
  "best_bid": {"price": 42000.0, "size": 1.5},
  "best_ask": {"price": 42001.0, "size": 0.8},
  "spread": 1.0,
  "mid_price": 42000.5,
  "update_id": 123456,
  "timestamp": 1705312200000
}
```

---

### `GET /orderbook-deltas/{symbol}`

Get recent orderbook delta updates.

**Parameters:**
| Name | In | Type | Default | Description |
|------|-----|------|---------|-------------|
| `symbol` | path | string | — | Trading pair |
| `limit` | query | integer | `50` | Max results (1-200) |

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "count": 50,
  "deltas": [
    {
      "symbol": "BTCUSDT",
      "delete": [],
      "update": [["42000.0", "2.0"]],
      "insert": [["41999.5", "0.5"]],
      "timestamp": 1705312200000
    }
  ]
}
```

---

### `GET /ticker/{symbol}`

Get the latest 24hr ticker.

**Response:** Full ticker with mark/index price, funding rate, open interest, etc.

---

### `GET /ticker-history/{symbol}`

Get historical ticker snapshots.

**Parameters:**
| Name | In | Type | Default | Description |
|------|-----|------|---------|-------------|
| `limit` | query | integer | `100` | Max results (1-500) |

---

### `GET /klines/{symbol}`

Get recent kline/candlestick data.

**Parameters:**
| Name | In | Type | Default | Description |
|------|-----|------|---------|-------------|
| `limit` | query | integer | `100` | Max results (1-500) |

---

## Analysis Endpoints

### `GET /analysis/vwap/{symbol}`

Calculate Volume-Weighted Average Price.

**Parameters:**
| Name | In | Type | Default | Description |
|------|-----|------|---------|-------------|
| `window` | query | integer | `100` | Number of trades (1-1000) |

**Response:** `VWAPResult`
```json
{
  "symbol": "BTCUSDT",
  "vwap": 42000.12345678,
  "window": 100,
  "total_volume": 123.456,
  "total_turnover": 5185012.345,
  "timestamp": "2026-01-15T10:30:00+00:00"
}
```

---

### `GET /analysis/rolling-stats/{symbol}`

Rolling mean, std, min, max over recent trades.

**Parameters:**
| Name | In | Type | Default | Description |
|------|-----|------|---------|-------------|
| `window` | query | integer | `200` | Number of trades (1-1000) |

**Response:** `RollingStats`

---

### `GET /analysis/spread/{symbol}`

Bid-ask spread analysis (absolute + basis points).

**Response:** `SpreadAnalysis`
```json
{
  "symbol": "BTCUSDT",
  "best_bid": 42000.0,
  "best_ask": 42001.0,
  "spread": 1.0,
  "spread_bps": 0.24,
  "mid_price": 42000.5,
  "timestamp": "2026-01-15T10:30:00+00:00"
}
```

---

### `GET /analysis/summary/{symbol}`

Comprehensive summary for a single symbol.

**Response:** `SymbolSummary` — includes last price, VWAP, rolling stats, spread, volume, 24h high/low.

---

### `GET /analysis/summary`

Summaries for all tracked symbols.

**Response:**
```json
{
  "count": 2,
  "connected": true,
  "summaries": [ ... ]
}
```

---

## Subscription Endpoints

### `POST /subscribe`

Subscribe to new symbols/topics.

**Request Body:** `SubscriptionRequest`
```json
{
  "symbols": ["SOLUSDT", "DOGEUSDT"],
  "topics": ["trades", "tickers"]
}
```

**Supported topics:** `trades`, `orderbook`, `tickers`, `klines`

**Response:**
```json
{
  "status": "subscribed",
  "topics": [
    "publicTrade.SOLUSDT",
    "tickers.SOLUSDT",
    "publicTrade.DOGEUSDT",
    "tickers.DOGEUSDT"
  ]
}
```

---

### `DELETE /subscribe`

Unsubscribe from symbols/topics.

Same request body format as `POST /subscribe`.

---

## WebSocket Streaming

### `ws://localhost:8000/ws/stream`

Real-time streaming of Bybit market data.

**Client Commands:**

```json
{"action": "subscribe", "symbols": ["BTCUSDT"]}
```

```json
{"action": "ping"}
```

**Server Responses:**

```json
{"type": "ack", "message": "Filter set to {'BTCUSDT'}"}
```

```json
{"type": "pong"}
```

Raw Bybit topic messages are forwarded as-is.
