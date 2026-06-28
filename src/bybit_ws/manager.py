"""Bybit V5 WebSocket connection manager with reconnection,
heartbeat, subscription, and message routing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

import websockets
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
    WebSocketException,
)

# websockets >= 14 uses ClientConnection with .state instead of .open
try:
    from websockets.protocol import State as WsState
    _HAS_STATE = True
except ImportError:
    try:
        from websockets.frames import State as WsState
        _HAS_STATE = True
    except ImportError:
        WsState = None  # type: ignore[assignment,misc]
        _HAS_STATE = False

from .config import MarketType, app_config, ws_config
from .models import (
    ConnectionStatus,
    KlineData,
    OrderBookDelta,
    OrderBookSnapshot,
    TickerData,
    TradeData,
)
from .store import DataStore

logger = logging.getLogger(__name__)


class BybitWebSocketManager:
    """Manages a persistent WebSocket connection to Bybit's V5 public API,
    with automatic reconnection, heartbeat, and topic-based message routing.

    Supports:
      - publicTrade.{symbol}
      - orderbook.{depth}.{symbol}
      - tickers.{symbol}
      - kline.{interval}.{symbol}

    Reconnection uses exponential backoff up to MAX_RECONNECT_ATTEMPTS.
    """

    def __init__(
        self,
        store: DataStore,
        market_type: Optional[MarketType] = None,
        on_message: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> None:
        self.store = store
        self.market_type = market_type or app_config.MARKET_TYPE
        self.on_message = on_message

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._should_reconnect = True
        self._reconnect_attempts = 0
        self._reconnect_task: Optional[asyncio.Task[None]] = None
        self._heartbeat_task: Optional[asyncio.Task[None]] = None

        self._last_ping: Optional[datetime] = None
        self._last_message: Optional[datetime] = None
        self._subscribed_topics: Set[str] = set()
        self._errors: List[str] = []
        self._max_errors = 20

        self._initial_topics = self._build_initial_topics()

    # ------------------------------------------------------------------
    # Topic construction
    # ------------------------------------------------------------------

    def _build_initial_topics(self) -> List[str]:
        """Build the full list of topic strings from config."""
        topics: List[str] = []
        for sym in ws_config.SYMBOLS:
            if app_config.SUBSCRIBE_TRADES:
                topics.append(f"publicTrade.{sym}")
            if app_config.SUBSCRIBE_ORDERBOOK:
                topics.append(f"orderbook.{ws_config.ORDERBOOK_DEPTH}.{sym}")
            if app_config.SUBSCRIBE_TICKERS:
                topics.append(f"tickers.{sym}")
            if app_config.SUBSCRIBE_KLINES:
                topics.append(f"kline.{ws_config.KLINE_INTERVAL}.{sym}")
        return topics

    def _parse_symbol_from_topic(self, topic: str) -> str:
        """Extract the symbol from a topic string like 'publicTrade.BTCUSDT'."""
        return topic.split(".")[-1]

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    @property
    def endpoint(self) -> str:
        """WebSocket endpoint URL for the configured market type."""
        return ws_config.ENDPOINTS[self.market_type]

    @property
    def is_connected(self) -> bool:
        """Whether the WebSocket is currently connected."""
        return self._connected

    def _is_ws_open(self) -> bool:
        """Check if the WebSocket is open (compatible with websockets 12-16)."""
        if self._ws is None:
            return False
        if _HAS_STATE:
            return self._ws.state == WsState.OPEN
        return getattr(self._ws, "open", False)

    async def connect(self) -> None:
        """Start the connection loop (with auto-reconnect)."""
        logger.info(
            "Starting Bybit WebSocket manager for %s market at %s",
            self.market_type.value,
            self.endpoint,
        )
        self._reconnect_task = asyncio.create_task(self._connection_loop())

    async def _connection_loop(self) -> None:
        """Main connection loop with reconnection logic."""
        while self._should_reconnect:
            try:
                await self._connect_and_listen()
            except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as e:
                logger.warning("WebSocket connection closed: %s", e)
                self._record_error(f"Connection closed: {e}")
            except WebSocketException as e:
                logger.error("WebSocket error: %s", e)
                self._record_error(f"WebSocket error: {e}")
            except Exception as e:
                logger.error("Unexpected error in connection loop: %s", e, exc_info=True)
                self._record_error(f"Unexpected error: {e}")
            finally:
                self._connected = False

            if not self._should_reconnect:
                break

            self._reconnect_attempts += 1
            if (
                ws_config.MAX_RECONNECT_ATTEMPTS > 0
                and self._reconnect_attempts > ws_config.MAX_RECONNECT_ATTEMPTS
            ):
                logger.error(
                    "Max reconnection attempts (%d) reached. Stopping.",
                    ws_config.MAX_RECONNECT_ATTEMPTS,
                )
                break

            delay = min(
                ws_config.RECONNECT_INTERVAL * (2 ** (self._reconnect_attempts - 1)),
                60.0,
            )
            logger.info("Reconnecting in %.1fs (attempt %d)...", delay, self._reconnect_attempts)
            await asyncio.sleep(delay)

        logger.info("WebSocket connection loop ended.")

    async def _connect_and_listen(self) -> None:
        """Establish connection, subscribe, and start listening."""
        logger.info("Connecting to %s ...", self.endpoint)
        self._ws = await websockets.connect(
            self.endpoint,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=5,
            max_size=2**22,
        )
        self._connected = True
        self._reconnect_attempts = 0
        logger.info("WebSocket connected to %s", self.endpoint)

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        if self._initial_topics:
            await self._subscribe(self._initial_topics)

        try:
            async for raw_message in self._ws:
                self._last_message = datetime.now(timezone.utc)
                await self._handle_raw_message(raw_message)
        finally:
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def _heartbeat_loop(self) -> None:
        """Send periodic ping to keep the connection alive."""
        try:
            while self._connected:
                await asyncio.sleep(ws_config.PING_INTERVAL)
                if self._ws and self._is_ws_open():
                    await self._ws.send(json.dumps({"op": "ping"}))
                    self._last_ping = datetime.now(timezone.utc)
                    logger.debug("Sent ping")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Heartbeat error: %s", e)
            self._record_error(f"Heartbeat error: {e}")

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def _handle_raw_message(self, raw: str) -> None:
        """Parse and route a raw WebSocket message."""
        try:
            msg: Dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON message: %s | raw: %s", e, raw[:200])
            self.store.increment_errors()
            return

        if "op" in msg:
            await self._handle_op_response(msg)
            return

        if "topic" in msg:
            if self.on_message:
                await self.on_message(msg)
            await self._route_message(msg)
            return

        logger.debug("Unrecognized message: %s", msg)

    async def _handle_op_response(self, msg: Dict[str, Any]) -> None:
        """Handle subscription/unsubscription/ping/pong responses."""
        op = msg.get("op")
        success = msg.get("success", False)
        if op == "subscribe":
            if success:
                logger.info("Subscribed successfully: %s", msg.get("ret_msg", ""))
            else:
                logger.error("Subscription failed: %s", msg.get("ret_msg", ""))
                self._record_error(f"Subscription failed: {msg.get('ret_msg', '')}")
        elif op == "unsubscribe":
            if success:
                logger.info("Unsubscribed: %s", msg.get("ret_msg", ""))
            else:
                logger.error("Unsubscribe failed: %s", msg.get("ret_msg", ""))
        elif op == "pong":
            logger.debug("Received pong")
        else:
            logger.debug("Op response: %s", msg)

    async def _route_message(self, msg: Dict[str, Any]) -> None:
        """Route a topic message to the appropriate handler based on topic type."""
        topic = msg.get("topic", "")
        msg_type = msg.get("type", "")
        ts = msg.get("ts")
        data = msg.get("data")

        try:
            if topic.startswith("publicTrade."):
                await self._handle_trade_message(topic, msg_type, ts, data)
            elif topic.startswith("orderbook."):
                await self._handle_orderbook_message(topic, msg_type, ts, data)
            elif topic.startswith("tickers."):
                await self._handle_ticker_message(topic, msg_type, ts, data)
            elif topic.startswith("kline."):
                await self._handle_kline_message(topic, msg_type, ts, data)
            else:
                logger.debug("Unhandled topic: %s", topic)
        except Exception as e:
            logger.error("Error processing message for topic '%s': %s", topic, e, exc_info=True)
            self.store.increment_errors()

    async def _handle_trade_message(self, topic: str, msg_type: str, ts: int, data: list) -> None:
        """Parse and store trade data."""
        symbol = self._parse_symbol_from_topic(topic)
        trades: List[TradeData] = []
        for item in data:
            try:
                trades.append(TradeData(**item))
            except Exception as e:
                logger.error("Invalid trade data %s: %s", item, e)
                self.store.increment_errors()
        if trades:
            await self.store.add_trades(symbol, trades)

    async def _handle_orderbook_message(self, topic: str, msg_type: str, ts: int, data: dict) -> None:
        """Parse and store orderbook snapshot or delta."""
        symbol = data.get("s", self._parse_symbol_from_topic(topic))

        if msg_type == "snapshot":
            snapshot = OrderBookSnapshot(
                symbol=symbol,
                bids=data.get("b", []),
                asks=data.get("a", []),
                timestamp=ts,
                update_id=data.get("u", 0),
            )
            await self.store.update_orderbook_snapshot(snapshot)

        elif msg_type == "delta":
            delta_data = data.get("d", [])
            deletes: List[List[str]] = []
            updates: List[List[str]] = []
            inserts: List[List[str]] = []
            for op in delta_data:
                if len(op) >= 2:
                    action = op[0]
                    level = [op[1], op[2] if len(op) > 2 else "0"]
                    if action == "delete":
                        deletes.append(level)
                    elif action == "update":
                        updates.append(level)
                    elif action == "insert":
                        inserts.append(level)

            delta = OrderBookDelta(
                symbol=symbol,
                delete=deletes,
                update=updates,
                insert=inserts,
                timestamp=ts,
            )
            await self.store.update_orderbook_delta(delta)
            await self._apply_delta_to_snapshot(symbol, delta)

    async def _apply_delta_to_snapshot(self, symbol: str, delta: OrderBookDelta) -> None:
        """Apply a delta update to the cached orderbook snapshot."""
        ob = await self.store.get_orderbook(symbol)
        if ob is None:
            return

        def _find_level(levels: List[List[str]], price: str) -> int:
            for i, lvl in enumerate(levels):
                if float(lvl[0]) == float(price):
                    return i
            return -1

        for price, _ in delta.delete:
            for levels in [ob.bids, ob.asks]:
                idx = _find_level(levels, price)
                if idx >= 0:
                    levels.pop(idx)

        for price, size in delta.update:
            for levels in [ob.bids, ob.asks]:
                idx = _find_level(levels, price)
                if idx >= 0:
                    levels[idx][1] = size

        for price, size in delta.insert:
            bb = ob.best_bid.price if ob.best_bid else 0
            ba = ob.best_ask.price if ob.best_ask else float("inf")
            mid = (bb + ba) / 2 if bb and ba and bb < ba else 0
            if mid and float(price) <= mid:
                ob.bids.append([price, size])
            else:
                ob.asks.append([price, size])

        ob.bids.sort(key=lambda x: float(x[0]), reverse=True)
        ob.asks.sort(key=lambda x: float(x[0]))

    async def _handle_ticker_message(self, topic: str, msg_type: str, ts: int, data: dict) -> None:
        """Parse and store ticker data."""
        try:
            symbol = data.get("symbol", self._parse_symbol_from_topic(topic))
            existing = await self.store.get_ticker(symbol)
            merged = existing.model_dump() if existing else {}
            merged.update(data)
            ticker = TickerData(**merged)
            await self.store.update_ticker(symbol, ticker)
        except Exception as e:
            logger.error("Invalid ticker data: %s | %s", data, e)
            self.store.increment_errors()

    async def _handle_kline_message(self, topic: str, msg_type: str, ts: int, data: list) -> None:
        """Parse and store kline data."""
        symbol = self._parse_symbol_from_topic(topic)
        for item in data:
            try:
                if "timestamp" not in item:
                    item["timestamp"] = ts
                kline = KlineData(**item)
                await self.store.add_kline(symbol, kline)
            except Exception as e:
                logger.error("Invalid kline data %s: %s", item, e)
                self.store.increment_errors()

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    async def _subscribe(self, topics: List[str]) -> None:
        """Send a subscribe request for the given topics."""
        if not self._ws or not self._is_ws_open():
            logger.warning("Cannot subscribe: WebSocket not connected")
            return
        await self._ws.send(json.dumps({"op": "subscribe", "args": topics}))
        self._subscribed_topics.update(topics)
        logger.info("Sent subscribe request for %d topics: %s", len(topics), topics[:5])

    async def subscribe(self, topics: List[str]) -> None:
        """Subscribe to additional topics at runtime."""
        if self._connected:
            await self._subscribe(topics)
        else:
            self._initial_topics.extend(topics)
            logger.info("WebSocket not connected; queued %d topics for subscription", len(topics))

    async def unsubscribe(self, topics: List[str]) -> None:
        """Unsubscribe from specific topics."""
        if not self._ws or not self._is_ws_open():
            logger.warning("Cannot unsubscribe: WebSocket not connected")
            return
        await self._ws.send(json.dumps({"op": "unsubscribe", "args": topics}))
        self._subscribed_topics.difference_update(topics)
        logger.info("Sent unsubscribe request for: %s", topics)

    # ------------------------------------------------------------------
    # Status & utilities
    # ------------------------------------------------------------------

    def _record_error(self, error: str) -> None:
        """Record an error in the error log (bounded)."""
        ts_str = datetime.now(timezone.utc).isoformat()
        self._errors.append(f"[{ts_str}] {error}")
        if len(self._errors) > self._max_errors:
            self._errors = self._errors[-self._max_errors:]

    def get_status(self) -> ConnectionStatus:
        """Return current connection status."""
        return ConnectionStatus(
            market_type=self.market_type.value,
            is_connected=self._connected,
            reconnect_attempts=self._reconnect_attempts,
            last_ping=self._last_ping,
            last_message=self._last_message,
            topics_subscribed=sorted(self._subscribed_topics),
            errors=self._errors[-10:],
        )

    async def disconnect(self) -> None:
        """Gracefully disconnect the WebSocket."""
        logger.info("Disconnecting Bybit WebSocket...")
        self._should_reconnect = False

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            if self._is_ws_open():
                await self._ws.close(code=1000, reason="Graceful shutdown")
            self._ws = None

        self._connected = False
        logger.info("Bybit WebSocket disconnected.")
