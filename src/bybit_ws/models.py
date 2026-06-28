"""Pydantic data models for Bybit WebSocket market data validation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Raw incoming message models (from Bybit WebSocket)
# ---------------------------------------------------------------------------

class TradeData(BaseModel):
    """Individual trade record from publicTrade topic."""

    T: int = Field(..., description="Timestamp in milliseconds")
    s: str = Field(..., description="Symbol, e.g. BTCUSDT")
    S: str = Field(..., description="Side: Buy or Sell")
    v: str = Field(..., description="Trade quantity (string)")
    p: str = Field(..., description="Trade price (string)")
    L: str = Field(..., description="Trade ID")
    BT: bool = Field(False, description="Whether it is a block trade")

    @property
    def price(self) -> float:
        return float(self.p)

    @property
    def quantity(self) -> float:
        return float(self.v)

    @property
    def timestamp_dt(self) -> datetime:
        return datetime.fromtimestamp(self.T / 1000.0, tz=timezone.utc)


class TradeMessage(BaseModel):
    """WebSocket message for trade topic."""

    topic: str
    type: str = Field(..., description="Message type: snapshot or delta")
    ts: int = Field(..., description="Message timestamp in ms")
    data: List[TradeData]


class OrderBookLevel(BaseModel):
    """A single price level in the order book."""

    price: float
    size: float


class OrderBookSnapshot(BaseModel):
    """Order book snapshot from orderbook.{depth}.{symbol} topic."""

    symbol: str
    bids: List[List[str]] = Field(..., description="[[price, size], ...]")
    asks: List[List[str]] = Field(..., description="[[price, size], ...]")
    timestamp: int
    update_id: int

    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        if not self.bids:
            return None
        return OrderBookLevel(price=float(self.bids[0][0]), size=float(self.bids[0][1]))

    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        if not self.asks:
            return None
        return OrderBookLevel(price=float(self.asks[0][0]), size=float(self.asks[0][1]))

    @property
    def spread(self) -> Optional[float]:
        bb = self.best_bid
        ba = self.best_ask
        if bb is None or ba is None:
            return None
        return ba.price - bb.price

    @property
    def mid_price(self) -> Optional[float]:
        bb = self.best_bid
        ba = self.best_ask
        if bb is None or ba is None:
            return None
        return (ba.price + bb.price) / 2.0


class OrderBookDelta(BaseModel):
    """Order book delta update from delta topic."""

    symbol: str
    delete: List[List[str]]
    update: List[List[str]]
    insert: List[List[str]]
    timestamp: int


class TickerData(BaseModel):
    """24hr ticker data from tickers.{symbol} topic.

    Bybit sends the first message as a full snapshot, then partial delta
    updates containing only changed fields. The data store merges these.
    """

    symbol: str
    lastPrice: str = Field("", description="Last traded price")
    highPrice24h: str = Field("", description="24h high")
    lowPrice24h: str = Field("", description="24h low")
    prevPrice24h: str = Field("", description="Price 24h ago")
    volume24h: str = Field("", description="24h volume (base)")
    turnover24h: str = Field("", description="24h turnover (quote)")
    price24hPcnt: str = Field("", description="24h price change percentage")
    tickDirection: str = Field("", description="Tick direction")
    prevPrice1h: str = Field("", description="Price 1h ago")
    markPrice: str = Field("", description="Mark price")
    indexPrice: str = Field("", description="Index price")
    openInterest: str = Field("", description="Open interest (base)")
    openInterestValue: str = Field("", description="Open interest value (quote)")
    fundingRate: str = Field("", description="Funding rate")
    fundingIntervalHour: str = Field("", description="Funding interval in hours")
    fundingCap: str = Field("", description="Funding cap")
    nextFundingTime: int = Field(0, description="Next funding time (ms)")
    bid1Price: str = Field("", description="Best bid price")
    bid1Size: str = Field("", description="Best bid size")
    ask1Price: str = Field("", description="Best ask price")
    ask1Size: str = Field("", description="Best ask size")

    @property
    def last_price(self) -> float:
        return float(self.lastPrice) if self.lastPrice else 0.0

    @property
    def volume_24h(self) -> float:
        return float(self.volume24h) if self.volume24h else 0.0

    @property
    def turnover_24h(self) -> float:
        return float(self.turnover24h) if self.turnover24h else 0.0

    @property
    def price_change_pct(self) -> float:
        return float(self.price24hPcnt) if self.price24hPcnt else 0.0

    @property
    def mark_price(self) -> float:
        return float(self.markPrice) if self.markPrice else 0.0

    @property
    def index_price(self) -> float:
        return float(self.indexPrice) if self.indexPrice else 0.0

    @property
    def best_bid_price(self) -> float:
        return float(self.bid1Price) if self.bid1Price else 0.0

    @property
    def best_ask_price(self) -> float:
        return float(self.ask1Price) if self.ask1Price else 0.0


class KlineData(BaseModel):
    """Kline/candlestick data from kline.{interval}.{symbol} topic."""

    start: int = Field(..., description="Kline start time (ms)")
    end: int = Field(..., description="Kline end time (ms)")
    interval: str
    open: str
    close: str
    high: str
    low: str
    volume: str
    turnover: str
    confirm: bool = Field(..., description="Whether the kline is confirmed (closed)")
    timestamp: int = Field(..., description="Kline update timestamp in ms")

    @property
    def open_price(self) -> float:
        return float(self.open)

    @property
    def close_price(self) -> float:
        return float(self.close)

    @property
    def high_price(self) -> float:
        return float(self.high)

    @property
    def low_price(self) -> float:
        return float(self.low)

    @property
    def volume_val(self) -> float:
        return float(self.volume)

    @property
    def turnover_val(self) -> float:
        return float(self.turnover)


# ---------------------------------------------------------------------------
# Analysis / Processed output models
# ---------------------------------------------------------------------------

class VWAPResult(BaseModel):
    """Volume-Weighted Average Price calculation result."""

    symbol: str
    vwap: float
    window: int
    total_volume: float
    total_turnover: float
    timestamp: datetime


class RollingStats(BaseModel):
    """Rolling statistics for a symbol."""

    symbol: str
    mean_price: float
    std_price: float
    min_price: float
    max_price: float
    trade_count: int
    window: int
    timestamp: datetime


class SpreadAnalysis(BaseModel):
    """Order book spread analysis."""

    symbol: str
    best_bid: float
    best_ask: float
    spread: float
    spread_bps: float
    mid_price: float
    timestamp: datetime


class SymbolSummary(BaseModel):
    """Comprehensive summary for a single symbol."""

    symbol: str
    last_price: Optional[float] = None
    vwap: Optional[float] = None
    rolling_mean: Optional[float] = None
    rolling_std: Optional[float] = None
    rolling_min: Optional[float] = None
    rolling_max: Optional[float] = None
    spread: Optional[float] = None
    spread_bps: Optional[float] = None
    mid_price: Optional[float] = None
    volume_24h: Optional[float] = None
    turnover_24h: Optional[float] = None
    price_change_pct_24h: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    trade_count: int = 0
    is_connected: bool = False
    last_update: Optional[datetime] = None


class ConnectionStatus(BaseModel):
    """WebSocket connection status."""

    market_type: str
    is_connected: bool
    reconnect_attempts: int
    last_ping: Optional[datetime] = None
    last_message: Optional[datetime] = None
    topics_subscribed: List[str] = []
    errors: List[str] = []


class SubscriptionRequest(BaseModel):
    """Request to subscribe to new topics."""

    symbols: List[str] = Field(..., description="Symbols to subscribe to")
    topics: List[str] = Field(..., description="Topic types: trades, orderbook, tickers, klines")


class SystemStats(BaseModel):
    """System-wide statistics."""

    total_symbols_tracked: int
    total_messages_received: int
    total_trades_processed: int
    total_errors: int
    uptime_seconds: float
    connections: List[ConnectionStatus]
