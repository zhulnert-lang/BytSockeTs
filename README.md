# bybit-ws

Real-time Bybit market data ingestion and analytics via WebSocket.

A professional Python library built on **FastAPI**, **Bybit V5 WebSocket API**, and **NumPy** that provides:

- Real-time WebSocket ingestion (trades, orderbook, tickers, klines)
- Automatic reconnection with exponential backoff
- In-memory analytics (VWAP, rolling stats, spread analysis)
- REST API with Swagger UI at `/docs`
- WebSocket streaming endpoint for real-time client consumption
- Dynamic subscription management at runtime

## Installation

```bash
# From the project root (editable install)
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
```

## Project Structure

```
BytSockeTs/
├── pyproject.toml              # PEP 621 packaging metadata
├── requirements.txt            # Dependencies (backward compat)
├── README.md
├── .gitignore
└── src/
    └── bybit_ws/               # Main package
        ├── __init__.py         # Public API exports
        ├── py.typed            # PEP 561 type-checker marker
        ├── app.py              # FastAPI application + REST endpoints
        ├── config.py           # MarketType, AppConfig, WebSocketConfig
        ├── models.py           # Pydantic data models
        ├── store.py            # DataStore (in-memory storage)
        ├── analytics.py        # DataProcessor (VWAP, rolling stats, spread)
        ├── manager.py          # BybitWebSocketManager (connection lifecycle)
        └── exceptions.py       # Custom exception hierarchy
```

## Quick Start

### Run the server

```bash
python -m bybit_ws.app
```

Then visit:
- **Swagger UI**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health
- **Market summary**: http://localhost:8000/analysis/summary

### Use as a library

```python
from bybit_ws import DataStore, DataProcessor, BybitWebSocketManager, MarketType

# Create independent instances
store = DataStore()
processor = DataProcessor(store)
manager = BybitWebSocketManager(store=store, market_type=MarketType.LINEAR)

# Start the WebSocket connection
await manager.connect()
```

### Mount in your own FastAPI app

```python
from fastapi import FastAPI
from bybit_ws.app import app as bybit_app

my_app = FastAPI()
my_app.mount("/market-data", bybit_app)
```

## Configuration

Edit `src/bybit_ws/config.py` or modify at runtime:

```python
from bybit_ws import app_config, ws_config, MarketType

# Change market type
app_config.MARKET_TYPE = MarketType.SPOT

# Add symbols
ws_config.SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# Adjust orderbook depth (1, 50, or 200)
ws_config.ORDERBOOK_DEPTH = 200

# Toggle topics
app_config.SUBSCRIBE_KLINES = False

# Adjust analysis windows
app_config.VWAP_WINDOW = 200

# Server settings
app_config.PORT = 9000
app_config.DEBUG = True
```

## API Reference

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info and endpoint listing |
| GET | `/health` | Connection health check + server time |
| GET | `/config` | Current system configuration |
| GET | `/status` | Detailed WebSocket connection status |
| GET | `/topics` | List subscribed topics |
| GET | `/stats` | System-wide statistics |

### Market Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/symbols` | List all tracked symbols |
| GET | `/trades/{symbol}?limit=100` | Recent trades |
| GET | `/orderbook/{symbol}?depth=50` | Latest orderbook snapshot |
| GET | `/orderbook-deltas/{symbol}?limit=50` | Recent orderbook delta updates |
| GET | `/ticker/{symbol}` | Latest 24hr ticker |
| GET | `/ticker-history/{symbol}?limit=100` | Historical ticker snapshots |
| GET | `/klines/{symbol}?limit=100` | Recent kline data |

### Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analysis/vwap/{symbol}?window=100` | VWAP calculation |
| GET | `/analysis/rolling-stats/{symbol}?window=200` | Rolling mean/std/min/max |
| GET | `/analysis/spread/{symbol}` | Bid-ask spread analysis |
| GET | `/analysis/summary/{symbol}` | Full summary for one symbol |
| GET | `/analysis/summary` | Summary for all symbols |

### Subscription Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/subscribe` | Subscribe to new symbols/topics |
| DELETE | `/subscribe` | Unsubscribe from symbols/topics |

```bash
# Subscribe to DOGEUSDT trades and tickers
curl -X POST http://localhost:8000/subscribe \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["DOGEUSDT"], "topics": ["trades", "tickers"]}'
```

### WebSocket Streaming

Connect to `ws://localhost:8000/ws/stream` to receive real-time market data.

```json
{"action": "subscribe", "symbols": ["BTCUSDT"]}
```

## Exceptions

```python
from bybit_ws import BybitWSError, BybitConnectionError, DataNotFoundError, SubscriptionError

try:
    ...
except BybitConnectionError:
    print("WebSocket connection failed")
except DataNotFoundError:
    print("Market data not available")
except SubscriptionError:
    print("Subscription request failed")
except BybitWSError:
    print("General bybit-ws error")
```

## Deployment

```bash
# Uvicorn (single worker — in-memory state)
uvicorn bybit_ws.app:app --host 0.0.0.0 --port 8000 --workers 1

# Docker
docker build -t bybit-ws .
docker run -p 8000:8000 bybit-ws
```

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["python", "-m", "bybit_ws.app"]
```

## Requirements

- Python >= 3.12
- fastapi >= 0.104.0
- uvicorn >= 0.24.0
- websockets >= 12.0
- pydantic >= 2.5.0
- numpy >= 1.26.0
