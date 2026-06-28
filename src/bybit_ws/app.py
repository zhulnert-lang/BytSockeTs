"""Bybit WebSocket FastAPI application.

Run directly:
    python -m bybit_ws.app

Or import the ``app`` instance to mount in your own FastAPI project:
    from bybit_ws.app import app
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .analytics import DataProcessor
from .config import MarketType, app_config, ws_config
from .models import (
    ConnectionStatus,
    KlineData,
    OrderBookDelta,
    OrderBookSnapshot,
    RollingStats,
    SpreadAnalysis,
    SubscriptionRequest,
    SymbolSummary,
    SystemStats,
    TickerData,
    TradeData,
    VWAPResult,
)
from .store import DataStore
from .manager import BybitWebSocketManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, app_config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bybit-ws")

# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------
data_store = DataStore()
data_processor = DataProcessor(data_store)
_market_type: MarketType = app_config.MARKET_TYPE
ws_manager = BybitWebSocketManager(
    store=data_store,
    market_type=_market_type,
)
_server_start_time: datetime = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ARG001
    """Start the WebSocket connection on startup, disconnect on shutdown."""
    logger.info("Starting Bybit FastAPI system...")
    await ws_manager.connect()
    logger.info("System ready. Listening on %s:%d", app_config.HOST, app_config.PORT)
    yield
    logger.info("Shutting down...")
    await ws_manager.disconnect()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Bybit WebSocket FastAPI System",
    description="""
## Real-time Market Data Ingestion & Analysis

Connects to Bybit V5 WebSocket public API and provides:

- **Trades** (`publicTrade.{symbol}`)
- **Order Book** (`orderbook.{depth}.{symbol}`) with delta updates
- **24hr Tickers** (`tickers.{symbol}`)
- **Klines** (`kline.{interval}.{symbol}`)

### Analytics

- **VWAP** — Volume-Weighted Average Price
- **Rolling Statistics** — Mean, std, min, max over trade window
- **Spread Analysis** — Bid-ask spread in absolute and basis points
- **Symbol Summary** — Aggregated view per symbol
""",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and return a structured JSON error response."""
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": str(exc),
            "path": str(request.url.path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Root & Health
# ---------------------------------------------------------------------------

@app.get("/", tags=["System"])
async def root() -> Dict[str, Any]:
    """API information and quick links."""
    return {
        "service": "Bybit WebSocket FastAPI System",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "config": "/config",
            "symbols": "/symbols",
            "trades": "/trades/{symbol}",
            "orderbook": "/orderbook/{symbol}",
            "orderbook_deltas": "/orderbook-deltas/{symbol}",
            "ticker": "/ticker/{symbol}",
            "ticker_history": "/ticker-history/{symbol}",
            "klines": "/klines/{symbol}",
            "vwap": "/analysis/vwap/{symbol}",
            "rolling_stats": "/analysis/rolling-stats/{symbol}",
            "spread": "/analysis/spread/{symbol}",
            "summary": "/analysis/summary",
            "summary_symbol": "/analysis/summary/{symbol}",
            "status": "/status",
            "topics": "/topics",
            "stats": "/stats",
            "stream": "/ws/stream",
        },
    }


@app.get("/health", tags=["System"])
async def health() -> Dict[str, Any]:
    """Health check — returns connection status and basic stats."""
    status = ws_manager.get_status()
    stats = await data_store.get_stats()
    return {
        "status": "healthy" if status.is_connected else "degraded",
        "connected": status.is_connected,
        "market_type": status.market_type,
        "symbols_tracked": stats["total_symbols_tracked"],
        "reconnect_attempts": status.reconnect_attempts,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "started_at": _server_start_time.isoformat(),
    }


@app.get("/config", tags=["System"])
async def get_config() -> Dict[str, Any]:
    """Expose the current system configuration."""
    return {
        "market_type": _market_type.value,
        "market_type_name": _market_type.name,
        "symbols": ws_config.SYMBOLS,
        "orderbook_depth": ws_config.ORDERBOOK_DEPTH,
        "kline_interval": ws_config.KLINE_INTERVAL,
        "subscribe_trades": app_config.SUBSCRIBE_TRADES,
        "subscribe_orderbook": app_config.SUBSCRIBE_ORDERBOOK,
        "subscribe_tickers": app_config.SUBSCRIBE_TICKERS,
        "subscribe_klines": app_config.SUBSCRIBE_KLINES,
        "vwap_window": app_config.VWAP_WINDOW,
        "rolling_stats_window": app_config.ROLLING_STATS_WINDOW,
        "max_reconnect_attempts": ws_config.MAX_RECONNECT_ATTEMPTS,
        "ping_interval": ws_config.PING_INTERVAL,
    }


# ---------------------------------------------------------------------------
# Market Data Endpoints
# ---------------------------------------------------------------------------

@app.get("/symbols", tags=["Market Data"])
async def get_symbols() -> Dict[str, Any]:
    """List all symbols currently being tracked."""
    symbols = await data_store.get_symbols()
    return {"symbols": symbols, "count": len(symbols)}


@app.get("/trades/{symbol}", tags=["Market Data"])
async def get_trades(symbol: str, limit: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
    """Get recent trades for a symbol."""
    trades: List[TradeData] = await data_store.get_trades(symbol.upper(), limit=limit)
    if not trades:
        raise HTTPException(status_code=404, detail=f"No trades found for {symbol}")
    return {
        "symbol": symbol.upper(),
        "count": len(trades),
        "trades": [
            {
                "id": t.L,
                "price": t.price,
                "quantity": t.quantity,
                "side": t.S,
                "timestamp": t.T,
                "timestamp_iso": t.timestamp_dt.isoformat(),
                "block_trade": t.BT,
            }
            for t in trades
        ],
    }


@app.get("/orderbook/{symbol}", tags=["Market Data"])
async def get_orderbook(symbol: str, depth: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    """Get the latest orderbook snapshot for a symbol."""
    ob: Optional[OrderBookSnapshot] = await data_store.get_orderbook(symbol.upper())
    if ob is None:
        raise HTTPException(status_code=404, detail=f"No orderbook data for {symbol}")

    bids_parsed = [{"price": float(b[0]), "size": float(b[1])} for b in ob.bids[:depth]]
    asks_parsed = [{"price": float(a[0]), "size": float(a[1])} for a in ob.asks[:depth]]

    return {
        "symbol": ob.symbol,
        "bids": bids_parsed,
        "asks": asks_parsed,
        "best_bid": ob.best_bid.model_dump() if ob.best_bid else None,
        "best_ask": ob.best_ask.model_dump() if ob.best_ask else None,
        "spread": ob.spread,
        "mid_price": ob.mid_price,
        "update_id": ob.update_id,
        "timestamp": ob.timestamp,
    }


@app.get("/ticker/{symbol}", tags=["Market Data"])
async def get_ticker(symbol: str) -> Dict[str, Any]:
    """Get the latest 24hr ticker for a symbol."""
    ticker: Optional[TickerData] = await data_store.get_ticker(symbol.upper())
    if ticker is None:
        raise HTTPException(status_code=404, detail=f"No ticker data for {symbol}")
    return {
        "symbol": ticker.symbol,
        "last_price": ticker.last_price,
        "high_24h": float(ticker.highPrice24h) if ticker.highPrice24h else None,
        "low_24h": float(ticker.lowPrice24h) if ticker.lowPrice24h else None,
        "prev_price_24h": float(ticker.prevPrice24h) if ticker.prevPrice24h else None,
        "prev_price_1h": float(ticker.prevPrice1h) if ticker.prevPrice1h else None,
        "volume_24h": ticker.volume_24h,
        "turnover_24h": ticker.turnover_24h,
        "price_change_pct_24h": ticker.price_change_pct,
        "mark_price": ticker.mark_price,
        "index_price": ticker.index_price,
        "tick_direction": ticker.tickDirection or None,
        "open_interest": float(ticker.openInterest) if ticker.openInterest else None,
        "open_interest_value": float(ticker.openInterestValue) if ticker.openInterestValue else None,
        "funding_rate": float(ticker.fundingRate) if ticker.fundingRate else None,
        "funding_interval_hour": float(ticker.fundingIntervalHour) if ticker.fundingIntervalHour else None,
        "next_funding_time": ticker.nextFundingTime if ticker.nextFundingTime else None,
        "bid1_price": ticker.best_bid_price,
        "bid1_size": float(ticker.bid1Size) if ticker.bid1Size else None,
        "ask1_price": ticker.best_ask_price,
        "ask1_size": float(ticker.ask1Size) if ticker.ask1Size else None,
    }


@app.get("/klines/{symbol}", tags=["Market Data"])
async def get_klines(symbol: str, limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    """Get recent kline (candlestick) data for a symbol."""
    klines: List[KlineData] = await data_store.get_klines(symbol.upper(), limit=limit)
    if not klines:
        raise HTTPException(status_code=404, detail=f"No kline data for {symbol}")
    return {
        "symbol": symbol.upper(),
        "count": len(klines),
        "klines": [
            {
                "start": k.start,
                "end": k.end,
                "interval": k.interval,
                "open": k.open_price,
                "close": k.close_price,
                "high": k.high_price,
                "low": k.low_price,
                "volume": k.volume_val,
                "turnover": k.turnover_val,
                "confirmed": k.confirm,
            }
            for k in klines
        ],
    }


@app.get("/orderbook-deltas/{symbol}", tags=["Market Data"])
async def get_orderbook_deltas(symbol: str, limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    """Get recent orderbook delta updates for a symbol."""
    deltas: List[OrderBookDelta] = await data_store.get_orderbook_deltas(symbol.upper(), limit=limit)
    if not deltas:
        raise HTTPException(status_code=404, detail=f"No orderbook delta data for {symbol}")
    return {
        "symbol": symbol.upper(),
        "count": len(deltas),
        "deltas": [
            {
                "symbol": d.symbol,
                "delete": d.delete,
                "update": d.update,
                "insert": d.insert,
                "timestamp": d.timestamp,
            }
            for d in deltas
        ],
    }


@app.get("/ticker-history/{symbol}", tags=["Market Data"])
async def get_ticker_history(symbol: str, limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    """Get historical ticker snapshots for a symbol."""
    history: List[TickerData] = await data_store.get_ticker_history(symbol.upper(), limit=limit)
    if not history:
        raise HTTPException(status_code=404, detail=f"No ticker history for {symbol}")
    return {
        "symbol": symbol.upper(),
        "count": len(history),
        "history": [
            {
                "symbol": t.symbol,
                "last_price": t.last_price,
                "volume_24h": t.volume_24h,
                "turnover_24h": t.turnover_24h,
                "price_change_pct": t.price_change_pct,
                "mark_price": t.mark_price,
                "index_price": t.index_price,
                "high_24h": float(t.highPrice24h) if t.highPrice24h else None,
                "low_24h": float(t.lowPrice24h) if t.lowPrice24h else None,
            }
            for t in history
        ],
    }


# ---------------------------------------------------------------------------
# Analysis Endpoints
# ---------------------------------------------------------------------------

@app.get("/analysis/vwap/{symbol}", tags=["Analysis"], response_model=VWAPResult)
async def get_vwap(symbol: str, window: Optional[int] = Query(None, ge=1, le=1000)) -> Dict[str, Any]:
    """Calculate VWAP (Volume-Weighted Average Price) for a symbol."""
    result = await data_processor.calculate_vwap(symbol.upper(), window=window)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient trade data for VWAP calculation: {symbol}",
        )
    return result.model_dump(mode="json")


@app.get("/analysis/rolling-stats/{symbol}", tags=["Analysis"], response_model=RollingStats)
async def get_rolling_stats(symbol: str, window: Optional[int] = Query(None, ge=1, le=1000)) -> Dict[str, Any]:
    """Calculate rolling mean, std, min, max for a symbol's recent trades."""
    result = await data_processor.calculate_rolling_stats(symbol.upper(), window=window)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient trade data for rolling stats: {symbol}",
        )
    return result.model_dump(mode="json")


@app.get("/analysis/spread/{symbol}", tags=["Analysis"], response_model=SpreadAnalysis)
async def get_spread_analysis(symbol: str) -> Dict[str, Any]:
    """Analyze the bid-ask spread for a symbol."""
    result = await data_processor.analyze_spread(symbol.upper())
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No orderbook data for spread analysis: {symbol}",
        )
    return result.model_dump(mode="json")


@app.get("/analysis/summary/{symbol}", tags=["Analysis"], response_model=SymbolSummary)
async def get_symbol_summary(symbol: str) -> Dict[str, Any]:
    """Get a comprehensive summary for a single symbol."""
    summary = await data_processor.get_symbol_summary(
        symbol.upper(),
        is_connected=ws_manager.is_connected,
    )
    return summary.model_dump(mode="json")


@app.get("/analysis/summary", tags=["Analysis"])
async def get_all_symbols_summary() -> Dict[str, Any]:
    """Get summaries for all tracked symbols."""
    summaries = await data_processor.get_all_symbols_summary(
        is_connected=ws_manager.is_connected,
    )
    return {
        "count": len(summaries),
        "connected": ws_manager.is_connected,
        "summaries": [s.model_dump(mode="json") for s in summaries],
    }


# ---------------------------------------------------------------------------
# Subscription Management
# ---------------------------------------------------------------------------

@app.post("/subscribe", tags=["Subscription"])
async def subscribe_topics(req: SubscriptionRequest) -> Dict[str, Any]:
    """Subscribe to additional topics.

    Topics supported: ``trades``, ``orderbook``, ``tickers``, ``klines``
    """
    topics: List[str] = []
    for sym in req.symbols:
        sym = sym.upper()
        for topic in req.topics:
            topic = topic.lower()
            if topic in ("trades", "trade", "publictrade"):
                topics.append(f"publicTrade.{sym}")
            elif topic in ("orderbook", "ob"):
                topics.append(f"orderbook.{ws_config.ORDERBOOK_DEPTH}.{sym}")
            elif topic in ("tickers", "ticker"):
                topics.append(f"tickers.{sym}")
            elif topic in ("klines", "kline"):
                topics.append(f"kline.{ws_config.KLINE_INTERVAL}.{sym}")

    if not topics:
        raise HTTPException(status_code=400, detail="No valid topics provided")

    await ws_manager.subscribe(topics)
    return {
        "status": "subscribed" if ws_manager.is_connected else "queued",
        "topics": topics,
    }


@app.delete("/subscribe", tags=["Subscription"])
async def unsubscribe_topics(req: SubscriptionRequest) -> Dict[str, Any]:
    """Unsubscribe from topics for given symbols."""
    topics: List[str] = []
    for sym in req.symbols:
        sym = sym.upper()
        for topic in req.topics:
            topic = topic.lower()
            if topic in ("trades", "trade", "publictrade"):
                topics.append(f"publicTrade.{sym}")
            elif topic in ("orderbook", "ob"):
                topics.append(f"orderbook.{ws_config.ORDERBOOK_DEPTH}.{sym}")
            elif topic in ("tickers", "ticker"):
                topics.append(f"tickers.{sym}")
            elif topic in ("klines", "kline"):
                topics.append(f"kline.{ws_config.KLINE_INTERVAL}.{sym}")

    if not topics:
        raise HTTPException(status_code=400, detail="No valid topics provided")

    await ws_manager.unsubscribe(topics)
    return {"status": "unsubscribed", "topics": topics}


# ---------------------------------------------------------------------------
# System Status
# ---------------------------------------------------------------------------

@app.get("/status", tags=["System"], response_model=ConnectionStatus)
async def get_connection_status() -> Dict[str, Any]:
    """Get detailed WebSocket connection status."""
    status = ws_manager.get_status()
    return status.model_dump(mode="json")


@app.get("/topics", tags=["System"])
async def get_subscribed_topics() -> Dict[str, Any]:
    """List all currently subscribed WebSocket topics."""
    status = ws_manager.get_status()
    return {
        "connected": status.is_connected,
        "count": len(status.topics_subscribed),
        "topics": status.topics_subscribed,
    }


@app.get("/stats", tags=["System"], response_model=SystemStats)
async def get_system_stats() -> SystemStats:
    """Get system-wide statistics."""
    stats = await data_store.get_stats()
    status = ws_manager.get_status()
    return SystemStats(
        total_symbols_tracked=stats["total_symbols_tracked"],
        total_messages_received=stats["total_messages_received"],
        total_trades_processed=stats["total_trades_processed"],
        total_errors=stats["total_errors"],
        uptime_seconds=stats["uptime_seconds"],
        connections=[status],
    )


# ---------------------------------------------------------------------------
# WebSocket Streaming Endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/stream")
async def stream_endpoint(websocket: WebSocket) -> None:
    """Stream real-time market data to connected clients.

    Send ``{"action": "subscribe", "symbols": ["BTCUSDT"]}`` to filter.
    """
    await websocket.accept()
    client_symbols: Optional[Set[str]] = None

    original_handler = ws_manager.on_message
    message_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=500)

    async def forward_handler(msg: Dict[str, Any]) -> None:
        """Forward messages to the client's queue, respecting symbol filter."""
        if client_symbols is not None:
            topic = msg.get("topic", "")
            symbol = topic.split(".")[-1]
            if symbol not in client_symbols:
                return
        try:
            message_queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass

    ws_manager.on_message = forward_handler

    try:
        async def receive_from_client() -> None:
            nonlocal client_symbols
            while True:
                raw = await websocket.receive_text()
                try:
                    cmd = json.loads(raw)
                    if cmd.get("action") == "subscribe":
                        syms = cmd.get("symbols", [])
                        client_symbols = {s.upper() for s in syms} if syms else None
                        await websocket.send_text(json.dumps({
                            "type": "ack",
                            "message": f"Filter set to {client_symbols or 'all'}",
                        }))
                    elif cmd.get("action") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON",
                    }))

        async def send_to_client() -> None:
            while True:
                msg = await message_queue.get()
                await websocket.send_text(json.dumps(msg))

        await asyncio.gather(receive_from_client(), send_to_client())

    except WebSocketDisconnect:
        logger.info("Streaming client disconnected")
    except Exception as e:
        logger.error("Stream endpoint error: %s", e)
    finally:
        ws_manager.on_message = original_handler


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "bybit_ws.app:app",
        host=app_config.HOST,
        port=app_config.PORT,
        reload=app_config.DEBUG,
        log_level=app_config.LOG_LEVEL.lower(),
    )
