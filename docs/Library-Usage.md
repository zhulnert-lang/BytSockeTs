# Library Usage

Use bybit-ws components independently in your own Python applications.

## Basic Usage

```python
import asyncio
from bybit_ws import DataStore, DataProcessor, BybitWebSocketManager, MarketType

async def main():
    # 1. Create instances
    store = DataStore()
    processor = DataProcessor(store)
    manager = BybitWebSocketManager(store=store, market_type=MarketType.LINEAR)

    # 2. Start WebSocket connection
    await manager.connect()

    # 3. Wait for data
    await asyncio.sleep(30)

    # 4. Query data
    trades = await store.get_trades("BTCUSDT", limit=10)
    ticker = await store.get_ticker("BTCUSDT")
    orderbook = await store.get_orderbook("BTCUSDT")

    # 5. Compute analytics
    vwap = await processor.calculate_vwap("BTCUSDT")
    stats = await processor.calculate_rolling_stats("BTCUSDT")
    spread = await processor.analyze_spread("BTCUSDT")
    summary = await processor.get_symbol_summary("BTCUSDT")

    # 6. Disconnect
    await manager.disconnect()

asyncio.run(main())
```

## Custom Market Type

```python
from bybit_ws import BybitWebSocketManager, DataStore, MarketType

store = DataStore()

# Spot market
spot_manager = BybitWebSocketManager(store=store, market_type=MarketType.SPOT)

# Inverse perpetual
inverse_manager = BybitWebSocketManager(store=store, market_type=MarketType.INVERSE)
```

## Custom Message Handler

Hook into raw WebSocket messages:

```python
from bybit_ws import BybitWebSocketManager, DataStore

store = DataStore()

async def my_handler(msg: dict):
    """Process every raw Bybit message."""
    topic = msg.get("topic", "")
    if "publicTrade" in topic:
        symbol = topic.split(".")[-1]
        data = msg.get("data", [])
        for trade in data:
            print(f"Trade: {symbol} @ {trade['p']} x {trade['v']}")

manager = BybitWebSocketManager(
    store=store,
    on_message=my_handler,  # Custom callback
)
await manager.connect()
```

## Runtime Subscriptions

```python
# Subscribe to new symbols at runtime
await manager.subscribe([
    "publicTrade.SOLUSDT",
    "tickers.SOLUSDT",
    "orderbook.50.SOLUSDT",
])

# Unsubscribe
await manager.unsubscribe(["tickers.SOLUSDT"])

# Check connection status
status = manager.get_status()
print(f"Connected: {status.is_connected}")
print(f"Topics: {status.topics_subscribed}")
```

## Accessing Stored Data

```python
# All symbols being tracked
symbols = await store.get_symbols()

# Recent trades
trades = await store.get_trades("BTCUSDT", limit=500)

# Orderbook snapshot
ob = await store.get_orderbook("BTCUSDT")
if ob:
    print(f"Best bid: {ob.best_bid.price}")
    print(f"Best ask: {ob.best_ask.price}")
    print(f"Spread: {ob.spread}")

# Orderbook deltas
deltas = await store.get_orderbook_deltas("BTCUSDT", limit=20)

# Ticker
ticker = await store.get_ticker("BTCUSDT")
if ticker:
    print(f"24h volume: {ticker.volume_24h}")
    print(f"Mark price: {ticker.mark_price}")
    print(f"Funding rate: {ticker.funding_rate}")

# Ticker history
history = await store.get_ticker_history("BTCUSDT", limit=100)

# Klines
klines = await store.get_klines("BTCUSDT", limit=60)

# System stats
stats = await store.get_stats()
print(f"Messages: {stats['total_messages_received']}")
print(f"Trades: {stats['total_trades_processed']}")
```

## Error Handling

```python
from bybit_ws import (
    BybitWSError,
    BybitConnectionError,
    DataNotFoundError,
    SubscriptionError,
    ConfigurationError,
)

try:
    vwap = await processor.calculate_vwap("UNKNOWNUSDT")
    if vwap is None:
        print("No data available")
except DataNotFoundError:
    print("Symbol not tracked")
except BybitConnectionError:
    print("WebSocket disconnected")
except BybitWSError as e:
    print(f"bybit-ws error: {e}")
```

## Configuration at Runtime

```python
from bybit_ws import app_config, ws_config, MarketType

# Change before creating the manager
app_config.MARKET_TYPE = MarketType.SPOT
ws_config.SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]
ws_config.ORDERBOOK_DEPTH = 200
app_config.VWAP_WINDOW = 500
app_config.ROLLING_STATS_WINDOW = 1000

# Now create manager with new config
manager = BybitWebSocketManager(store=store)
```

## FastAPI Integration

Mount the bybit-ws app in your own FastAPI application:

```python
from fastapi import FastAPI
from bybit_ws.app import app as bybit_app

my_app = FastAPI(title="My Trading Platform")

# Mount under a prefix
my_app.mount("/market-data", bybit_app)

# Your own endpoints
@my_app.get("/my-endpoint")
async def my_endpoint():
    return {"message": "Hello from my app"}

# Run: uvicorn my_module:my_app
```
