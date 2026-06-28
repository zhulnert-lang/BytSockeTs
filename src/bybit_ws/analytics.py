"""Real-time analytics engine for Bybit market data."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np

from .config import app_config
from .models import (
    RollingStats,
    SpreadAnalysis,
    SymbolSummary,
    VWAPResult,
)
from .store import DataStore

logger = logging.getLogger(__name__)


class DataProcessor:
    """Real-time analysis engine that computes VWAP, rolling statistics,
    spread analysis, and symbol summaries from the DataStore.
    """

    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def calculate_vwap(self, symbol: str, window: Optional[int] = None) -> Optional[VWAPResult]:
        """Calculate VWAP over the last N trades for a symbol."""
        w = window or app_config.VWAP_WINDOW
        trades = await self.store.get_trades(symbol, limit=w)
        if not trades:
            return None

        prices = np.array([t.price for t in trades])
        volumes = np.array([t.quantity for t in trades])
        total_vol = volumes.sum()
        total_turnover = (prices * volumes).sum()

        if total_vol == 0:
            return None

        vwap = total_turnover / total_vol
        return VWAPResult(
            symbol=symbol,
            vwap=round(vwap, 8),
            window=len(trades),
            total_volume=round(total_vol, 8),
            total_turnover=round(total_turnover, 8),
            timestamp=datetime.now(timezone.utc),
        )

    async def calculate_rolling_stats(self, symbol: str, window: Optional[int] = None) -> Optional[RollingStats]:
        """Calculate rolling mean, std, min, max over the last N trades."""
        w = window or app_config.ROLLING_STATS_WINDOW
        trades = await self.store.get_trades(symbol, limit=w)
        if not trades:
            return None

        prices = np.array([t.price for t in trades])
        return RollingStats(
            symbol=symbol,
            mean_price=round(float(prices.mean()), 8),
            std_price=round(float(prices.std()), 8),
            min_price=round(float(prices.min()), 8),
            max_price=round(float(prices.max()), 8),
            trade_count=len(prices),
            window=len(prices),
            timestamp=datetime.now(timezone.utc),
        )

    async def analyze_spread(self, symbol: str) -> Optional[SpreadAnalysis]:
        """Analyze the order book spread for a symbol."""
        ob = await self.store.get_orderbook(symbol)
        if ob is None or ob.best_bid is None or ob.best_ask is None:
            return None

        spread = ob.spread
        mid = ob.mid_price
        spread_bps = (spread / mid * 10000) if mid and mid > 0 else 0.0

        return SpreadAnalysis(
            symbol=symbol,
            best_bid=ob.best_bid.price,
            best_ask=ob.best_ask.price,
            spread=round(spread, 8),
            spread_bps=round(spread_bps, 2),
            mid_price=round(mid, 8),
            timestamp=datetime.now(timezone.utc),
        )

    async def get_symbol_summary(self, symbol: str, is_connected: bool = False) -> SymbolSummary:
        """Build a comprehensive summary for a single symbol."""
        trades = await self.store.get_trades(symbol, limit=1)
        last_price = trades[-1].price if trades else None

        vwap_result = await self.calculate_vwap(symbol)
        rolling = await self.calculate_rolling_stats(symbol)
        spread_analysis = await self.analyze_spread(symbol)
        ticker = await self.store.get_ticker(symbol)

        return SymbolSummary(
            symbol=symbol,
            last_price=last_price,
            vwap=vwap_result.vwap if vwap_result else None,
            rolling_mean=rolling.mean_price if rolling else None,
            rolling_std=rolling.std_price if rolling else None,
            rolling_min=rolling.min_price if rolling else None,
            rolling_max=rolling.max_price if rolling else None,
            spread=spread_analysis.spread if spread_analysis else None,
            spread_bps=spread_analysis.spread_bps if spread_analysis else None,
            mid_price=spread_analysis.mid_price if spread_analysis else None,
            volume_24h=ticker.volume_24h if ticker else None,
            turnover_24h=ticker.turnover_24h if ticker else None,
            price_change_pct_24h=ticker.price_change_pct if ticker else None,
            high_24h=float(ticker.highPrice24h) if ticker and ticker.highPrice24h else None,
            low_24h=float(ticker.lowPrice24h) if ticker and ticker.lowPrice24h else None,
            trade_count=len(await self.store.get_trades(symbol, limit=999999)),
            is_connected=is_connected,
            last_update=datetime.now(timezone.utc),
        )

    async def get_all_symbols_summary(self, is_connected: bool = False) -> List[SymbolSummary]:
        """Get summaries for all tracked symbols."""
        symbols = await self.store.get_symbols()
        summaries: List[SymbolSummary] = []
        for sym in symbols:
            summary = await self.get_symbol_summary(sym, is_connected)
            summaries.append(summary)
        return summaries
