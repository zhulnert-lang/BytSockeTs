"""Thread-safe in-memory data store for Bybit market data."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Set

from .config import ws_config
from .models import (
    KlineData,
    OrderBookDelta,
    OrderBookSnapshot,
    TickerData,
    TradeData,
)

logger = logging.getLogger(__name__)


class DataStore:
    """Thread-safe in-memory store for all Bybit market data.

    Maintains bounded deques for trades, orderbooks, tickers, and klines
    per symbol, and provides fast lookup for analysis queries.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

        self._trades: Dict[str, Deque[TradeData]] = defaultdict(
            lambda: deque(maxlen=ws_config.MAX_TRADES_PER_SYMBOL)
        )
        self._orderbooks: Dict[str, OrderBookSnapshot] = {}
        self._orderbook_deltas: Dict[str, Deque[OrderBookDelta]] = defaultdict(
            lambda: deque(maxlen=ws_config.MAX_ORDERBOOK_SNAPSHOTS)
        )
        self._tickers: Dict[str, TickerData] = {}
        self._ticker_history: Dict[str, Deque[TickerData]] = defaultdict(
            lambda: deque(maxlen=ws_config.MAX_TICKER_HISTORY)
        )
        self._klines: Dict[str, Deque[KlineData]] = defaultdict(
            lambda: deque(maxlen=ws_config.MAX_KLINE_HISTORY)
        )

        self._symbols: Set[str] = set()

        self._total_messages = 0
        self._total_trades = 0
        self._total_errors = 0
        self._start_time = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    async def add_trades(self, symbol: str, trades: List[TradeData]) -> None:
        """Add a batch of trades for a symbol."""
        async with self._lock:
            self._symbols.add(symbol)
            for t in trades:
                self._trades[symbol].append(t)
            self._total_trades += len(trades)
            self._total_messages += 1

    async def update_orderbook_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        """Store the latest orderbook snapshot for a symbol."""
        async with self._lock:
            self._symbols.add(snapshot.symbol)
            self._orderbooks[snapshot.symbol] = snapshot
            self._total_messages += 1

    async def update_orderbook_delta(self, delta: OrderBookDelta) -> None:
        """Apply an orderbook delta update."""
        async with self._lock:
            self._symbols.add(delta.symbol)
            self._orderbook_deltas[delta.symbol].append(delta)
            self._total_messages += 1

    async def update_ticker(self, symbol: str, ticker: TickerData) -> None:
        """Update the latest ticker for a symbol."""
        async with self._lock:
            self._symbols.add(symbol)
            self._tickers[symbol] = ticker
            self._ticker_history[symbol].append(ticker)
            self._total_messages += 1

    async def add_kline(self, symbol: str, kline: KlineData) -> None:
        """Add a kline update for a symbol."""
        async with self._lock:
            self._symbols.add(symbol)
            klines = self._klines[symbol]
            if klines and klines[-1].start == kline.start:
                klines[-1] = kline
            else:
                klines.append(kline)
            self._total_messages += 1

    def increment_errors(self) -> None:
        """Increment the error counter."""
        self._total_errors += 1

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    async def get_trades(self, symbol: str, limit: int = 100) -> List[TradeData]:
        """Get recent trades for a symbol."""
        async with self._lock:
            trades = list(self._trades.get(symbol, []))
            return trades[-limit:]

    async def get_orderbook(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """Get the latest orderbook snapshot for a symbol."""
        async with self._lock:
            return self._orderbooks.get(symbol)

    async def get_ticker(self, symbol: str) -> Optional[TickerData]:
        """Get the latest ticker for a symbol."""
        async with self._lock:
            return self._tickers.get(symbol)

    async def get_klines(self, symbol: str, limit: int = 100) -> List[KlineData]:
        """Get recent klines for a symbol."""
        async with self._lock:
            klines = list(self._klines.get(symbol, []))
            return klines[-limit:]

    async def get_orderbook_deltas(self, symbol: str, limit: int = 50) -> List[OrderBookDelta]:
        """Get recent orderbook delta updates for a symbol."""
        async with self._lock:
            deltas = list(self._orderbook_deltas.get(symbol, []))
            return deltas[-limit:]

    async def get_ticker_history(self, symbol: str, limit: int = 100) -> List[TickerData]:
        """Get ticker history for a symbol."""
        async with self._lock:
            history = list(self._ticker_history.get(symbol, []))
            return history[-limit:]

    async def get_symbols(self) -> List[str]:
        """Get all tracked symbols."""
        async with self._lock:
            return sorted(self._symbols)

    async def get_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            uptime = (now - self._start_time).total_seconds()
            return {
                "total_symbols_tracked": len(self._symbols),
                "total_messages_received": self._total_messages,
                "total_trades_processed": self._total_trades,
                "total_errors": self._total_errors,
                "uptime_seconds": round(uptime, 1),
            }
