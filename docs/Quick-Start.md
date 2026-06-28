# Quick Start Guide

Get bybit-ws running in under 5 minutes.

## 1. Clone and Install

```bash
git clone https://github.com/zhulnert-lang/BytSockeTs.git
cd BytSockeTs
pip install -e .
```

## 2. Run the Server

```bash
python -m bybit_ws.app
```

The server starts on `http://localhost:8000`.

## 3. Verify It Works

Open your browser:

- **Swagger UI**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Market Summary**: http://localhost:8000/analysis/summary

## 4. Try the API

```bash
# Check health
curl http://localhost:8000/health

# Get current config
curl http://localhost:8000/config

# Subscribe to a new symbol
curl -X POST http://localhost:8000/subscribe \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["SOLUSDT"], "topics": ["trades", "tickers"]}'
```

## 5. Use as a Library

```python
import asyncio
from bybit_ws import DataStore, DataProcessor, BybitWebSocketManager, MarketType

async def main():
    store = DataStore()
    processor = DataProcessor(store)
    manager = BybitWebSocketManager(store=store, market_type=MarketType.LINEAR)

    await manager.connect()
    await asyncio.sleep(10)

    vwap = await processor.calculate_vwap("BTCUSDT")
    print(f"BTCUSDT VWAP: {vwap.vwap if vwap else 'No data yet'}")

    await manager.disconnect()

asyncio.run(main())
```

## Next Steps

- Read the [REST API Reference](REST-API.md) for all 19 endpoints
- Learn about [Configuration](Configuration.md) options
- Explore [Library Usage](Library-Usage.md) patterns
