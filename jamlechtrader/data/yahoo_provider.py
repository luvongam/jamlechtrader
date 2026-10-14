"""Yahoo Finance data provider — historical bars, optimized polling, and WebSocket streaming."""

from __future__ import annotations

import json
import struct
import threading
import time
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pandas as pd
from loguru import logger

from jamlechtrader.core.enums import Timeframe
from jamlechtrader.core.models import Bar, Tick
from jamlechtrader.data.base import AbstractDataHandler

# ── Timeframe mapping ─────────────────────────────────────────────────

_TF_MAP: dict[str, str] = {
    "M1": "1m",
    "M2": "2m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
    "W1": "1wk",
    "MN1": "1mo",
}

_INTRADAY_TFS = {"1m", "2m", "5m", "15m", "30m", "1h"}
_MAX_INTRADAY_DAYS = {
    "1m": 7,
    "2m": 60,
    "5m": 60,
    "15m": 60,
    "30m": 60,
    "1h": 730,
}

# Minimal period to fetch for each interval when polling
_POLL_PERIOD: dict[str, str] = {
    "1m": "15m",
    "2m": "30m",
    "5m": "1h",
    "15m": "2h",
    "30m": "4h",
    "1h": "1d",
    "4h": "5d",
    "1d": "5d",
    "1wk": "1mo",
    "1mo": "3mo",
}


def _to_yf_interval(tf: Timeframe | str) -> str:
    """Convert our Timeframe enum to a yfinance interval string."""
    tf_str = tf.value if isinstance(tf, Timeframe) else tf
    interval = _TF_MAP.get(tf_str)
    if interval is None:
        raise ValueError(
            f"Timeframe {tf_str} is not supported by Yahoo Finance. "
            f"Supported: {list(_TF_MAP.keys())}"
        )
    return interval


def _symbol_to_yf(symbol: str) -> str:
    """Convert forex/crypto symbols to yfinance format.

    Examples:
        EURUSD -> EURUSD=X
        GBPUSD -> GBPUSD=X
        BTCUSD -> BTC-USD
        AAPL   -> AAPL (unchanged)
        XAUUSD -> GC=F (gold futures)
    """
    s = symbol.upper()

    # Crypto pairs
    crypto_bases = ("BTC", "ETH", "XRP", "SOL", "ADA", "DOGE", "DOT", "AVAX", "LINK", "MATIC")
    for base in crypto_bases:
        if s.startswith(base) and s.endswith("USD"):
            return f"{base}-USD"
        if s.startswith(base) and s.endswith("USDT"):
            return f"{base}-USD"

    # Commodity mappings
    commodity_map = {
        "XAUUSD": "GC=F",
        "XAGUSD": "SI=F",
        "WTIUSD": "CL=F",
        "USOIL": "CL=F",
    }
    if s in commodity_map:
        return commodity_map[s]

    # Forex pairs (6-char like EURUSD)
    forex_currencies = (
        "EUR", "USD", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF",
        "SEK", "NOK", "DKK", "SGD", "HKD", "ZAR", "MXN", "TRY",
    )
    if len(s) == 6:
        base, quote = s[:3], s[3:]
        if base in forex_currencies and quote in forex_currencies:
            return f"{s}=X"

    # Index mappings
    index_map = {
        "US30": "YM=F",
        "US500": "ES=F",
        "US100": "NQ=F",
        "SPX500": "^GSPC",
        "NAS100": "^IXIC",
        "DJ30": "^DJI",
        "DAX": "^GDAXI",
        "FTSE": "^FTSE",
    }
    if s in index_map:
        return index_map[s]

    # Default: pass through as-is (stocks, ETFs)
    return s


def _ensure_utc(ts) -> datetime:
    """Convert any timestamp to a timezone-aware UTC datetime."""
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _df_to_bars(df: pd.DataFrame, symbol: str) -> list[Bar]:
    """Convert yfinance DataFrame to list of Bar models."""
    bars = []
    for ts, row in df.iterrows():
        bars.append(
            Bar(
                symbol=symbol,
                timestamp=_ensure_utc(ts),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row.get("Volume", 0)),
                spread=0,
                tick_volume=float(row.get("Volume", 0)),
            )
        )
    return bars


# ── Historical data provider ──────────────────────────────────────────


class YahooFinanceProvider(AbstractDataHandler):
    """Provides historical bars from Yahoo Finance via yfinance."""

    def __init__(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        start: datetime,
        end: datetime,
        auto_adjust: bool = True,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe if isinstance(timeframe, Timeframe) else Timeframe(timeframe)
        self.start = start
        self.end = end
        self.auto_adjust = auto_adjust
        self._yf_symbol = _symbol_to_yf(symbol)
        self._yf_interval = _to_yf_interval(self.timeframe)
        self._bars: list[Bar] = []
        self._index = 0

    def load(self) -> None:
        """Download data from Yahoo Finance."""
        import yfinance as yf

        logger.info(
            f"Downloading {self._yf_symbol} ({self.symbol}) "
            f"{self._yf_interval} from Yahoo Finance: {self.start} -> {self.end}"
        )

        # Enforce intraday limits
        if self._yf_interval in _INTRADAY_TFS:
            max_days = _MAX_INTRADAY_DAYS.get(self._yf_interval, 60)
            earliest = datetime.now() - timedelta(days=max_days)
            if self.start < earliest:
                logger.warning(
                    f"Yahoo Finance only provides {max_days} days of "
                    f"{self._yf_interval} data. Adjusting start to {earliest.date()}"
                )
                self.start = earliest

        ticker = yf.Ticker(self._yf_symbol)
        df = ticker.history(
            start=self.start.strftime("%Y-%m-%d"),
            end=self.end.strftime("%Y-%m-%d"),
            interval=self._yf_interval,
            auto_adjust=self.auto_adjust,
        )

        if df.empty:
            logger.warning(f"No data returned from Yahoo Finance for {self._yf_symbol}")
            self._bars = []
            return

        self._bars = _df_to_bars(df, self.symbol)
        self._index = 0
        logger.info(f"Loaded {len(self._bars)} bars for {self.symbol} from Yahoo Finance")

    def bars(self) -> Iterator[Bar]:
        self._index = 0
        for bar in self._bars:
            self._index += 1
            yield bar

    def has_next(self) -> bool:
        return self._index < len(self._bars)

    def get_all_bars(self) -> list[Bar]:
        return list(self._bars)


# ── Optimized polling live feed ───────────────────────────────────────


class YahooLiveFeed:
    """Polls Yahoo Finance for the latest bar with optimized fetches.

    Improvements over naive polling:
    - Uses minimal period (e.g. "15m" not "1d") to reduce download size
    - Falls back to fast_info for sub-second price snapshots between bars
    - Forex and crypto are near-real-time; equities have ~15 min delay

    Usage::

        feed = YahooLiveFeed("EURUSD", timeframe="M5", poll_interval=10.0)
        bar = feed.get_latest_bar()     # one-shot
        tick = feed.get_snapshot_tick()  # lightweight current price
        feed.start(event_bus)           # blocking loop
    """

    def __init__(
        self,
        symbol: str,
        timeframe: Timeframe | str = "M1",
        poll_interval: float = 5.0,
    ) -> None:
        import yfinance as yf

        self.symbol = symbol
        self.timeframe = timeframe if isinstance(timeframe, Timeframe) else Timeframe(timeframe)
        self.poll_interval = poll_interval
        self._yf_symbol = _symbol_to_yf(symbol)
        self._yf_interval = _to_yf_interval(self.timeframe)
        self._poll_period = _POLL_PERIOD.get(self._yf_interval, "1d")
        self._ticker = yf.Ticker(self._yf_symbol)
        self._running = False
        self._last_bar_time: datetime | None = None

    def get_snapshot_tick(self) -> Tick | None:
        """Get a lightweight price snapshot via fast_info (no history download).

        Returns a Tick with the current market price. For most instruments,
        bid and ask are approximated from the last price with a small spread.
        """
        try:
            info = self._ticker.fast_info
            price = float(info.last_price)
            now = datetime.now(tz=timezone.utc)

            # Approximate bid/ask — fast_info doesn't provide them directly
            day_range = float(info.day_high - info.day_low) if info.day_high else 0
            half_spread = max(day_range * 0.0001, price * 0.00005)

            return Tick(
                symbol=self.symbol,
                timestamp=now,
                bid=round(price - half_spread, 6),
                ask=round(price + half_spread, 6),
                last=price,
                volume=float(info.last_volume or 0),
            )
        except Exception as e:
            logger.error(f"fast_info snapshot failed for {self._yf_symbol}: {e}")
            return None

    def get_latest_bar(self) -> Bar | None:
        """Get the most recent bar using a minimal history fetch."""
        try:
            df = self._ticker.history(period=self._poll_period, interval=self._yf_interval)
            if df.empty:
                return None
            last_row = df.iloc[-1]
            return Bar(
                symbol=self.symbol,
                timestamp=_ensure_utc(df.index[-1]),
                open=float(last_row["Open"]),
                high=float(last_row["High"]),
                low=float(last_row["Low"]),
                close=float(last_row["Close"]),
                volume=float(last_row.get("Volume", 0)),
            )
        except Exception as e:
            logger.error(f"Failed to get latest bar: {e}")
            return None

    def start(self, event_bus) -> None:
        """Start polling for new bars. Blocks until stop() is called."""
        from jamlechtrader.core.events import MarketEvent

        self._running = True
        logger.info(
            f"YahooLiveFeed started for {self.symbol} ({self._yf_symbol}) "
            f"interval={self._yf_interval} poll_period={self._poll_period}"
        )

        while self._running:
            try:
                df = self._ticker.history(period=self._poll_period, interval=self._yf_interval)
                if not df.empty:
                    bar_time = _ensure_utc(df.index[-1])
                    if bar_time != self._last_bar_time:
                        self._last_bar_time = bar_time
                        last_row = df.iloc[-1]
                        bar = Bar(
                            symbol=self.symbol,
                            timestamp=bar_time,
                            open=float(last_row["Open"]),
                            high=float(last_row["High"]),
                            low=float(last_row["Low"]),
                            close=float(last_row["Close"]),
                            volume=float(last_row.get("Volume", 0)),
                        )
                        event = MarketEvent(
                            symbol=self.symbol,
                            timestamp=bar_time,
                            data=bar,
                        )
                        event_bus.publish(event)
            except Exception as e:
                logger.error(f"YahooLiveFeed error: {e}")

            time.sleep(self.poll_interval)

    def stop(self) -> None:
        self._running = False
        logger.info(f"YahooLiveFeed stopped for {self.symbol}")


# ── WebSocket real-time streaming ─────────────────────────────────────

# Yahoo Finance uses a protobuf-based WebSocket endpoint for streaming quotes.
# The public endpoint is wss://streamer.finance.yahoo.com/ — it accepts
# subscription messages as JSON and pushes binary protobuf price updates.
#
# This is a lightweight decoder that extracts price fields from the protobuf
# wire format without requiring the google.protobuf library.


def _decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    """Decode a protobuf varint, return (value, new_offset)."""
    result = 0
    shift = 0
    while offset < len(data):
        b = data[offset]
        offset += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result, offset
        shift += 7
    return result, offset


def _decode_protobuf_fields(data: bytes) -> dict[int, float | int | str | bytes]:
    """Decode protobuf wire format into field_number -> value dict.

    Handles: varint (type 0), 64-bit fixed (type 1), length-delimited (type 2),
    and 32-bit fixed (type 5). Floats are decoded from fixed fields.
    """
    fields: dict[int, float | int | str | bytes] = {}
    offset = 0
    while offset < len(data):
        tag, offset = _decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 0:  # varint
            value, offset = _decode_varint(data, offset)
            fields[field_number] = value
        elif wire_type == 1:  # 64-bit (double)
            value = struct.unpack("<d", data[offset : offset + 8])[0]
            offset += 8
            fields[field_number] = value
        elif wire_type == 2:  # length-delimited (string/bytes)
            length, offset = _decode_varint(data, offset)
            raw = data[offset : offset + length]
            offset += length
            try:
                fields[field_number] = raw.decode("utf-8")
            except UnicodeDecodeError:
                fields[field_number] = raw
        elif wire_type == 5:  # 32-bit (float)
            value = struct.unpack("<f", data[offset : offset + 4])[0]
            offset += 4
            fields[field_number] = value
        else:
            break  # Unknown wire type, stop parsing

    return fields


class YahooWebSocketFeed:
    """Real-time tick streaming via Yahoo Finance WebSocket.

    Connects to Yahoo's public streaming endpoint and receives price
    updates as protobuf messages. Delivers Tick objects through callbacks
    or an EventBus.

    Typical latency: <1 second for US equities during market hours,
    near-instant for crypto (24/7).

    Usage::

        feed = YahooWebSocketFeed(["AAPL", "EURUSD", "BTCUSD"])

        # Callback style
        feed.on_tick = lambda tick: print(tick)
        feed.start()  # blocking

        # Or with EventBus
        feed.start(event_bus)  # publishes MarketEvent(data=Tick)

        # Background thread
        feed.start_background()
        # ... do other work ...
        feed.stop()
    """

    WS_URL = "wss://streamer.finance.yahoo.com/"

    def __init__(
        self,
        symbols: list[str] | str,
        on_tick: callable | None = None,
    ) -> None:
        if isinstance(symbols, str):
            symbols = [symbols]
        self.symbols = symbols
        self._yf_symbols = [_symbol_to_yf(s) for s in symbols]
        # Reverse mapping: yf_symbol -> our symbol
        self._symbol_map = dict(zip(self._yf_symbols, symbols))
        self.on_tick = on_tick
        self._running = False
        self._thread: threading.Thread | None = None
        self._ws = None
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0

    def start(self, event_bus=None) -> None:
        """Start streaming. Blocks until stop() is called.

        Args:
            event_bus: Optional EventBus to publish MarketEvent(data=Tick).
        """
        self._running = True
        while self._running:
            try:
                self._connect_and_stream(event_bus)
            except Exception as e:
                if not self._running:
                    break
                logger.error(f"WebSocket error: {e}")
                logger.info(f"Reconnecting in {self._reconnect_delay:.0f}s...")
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )

    def start_background(self, event_bus=None) -> threading.Thread:
        """Start streaming in a background daemon thread."""
        self._thread = threading.Thread(
            target=self.start, args=(event_bus,), daemon=True, name="yahoo-ws-feed"
        )
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        """Stop streaming and close the WebSocket."""
        self._running = False
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("YahooWebSocketFeed stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def _connect_and_stream(self, event_bus) -> None:
        """Single WebSocket connection lifecycle."""
        import websocket

        logger.info(
            f"Connecting to Yahoo WebSocket for {self._yf_symbols}..."
        )

        ws = websocket.create_connection(
            self.WS_URL,
            timeout=30,
            header={"User-Agent": "Mozilla/5.0"},
        )
        self._ws = ws

        # Subscribe to symbols
        subscribe_msg = json.dumps({"subscribe": self._yf_symbols})
        ws.send(subscribe_msg)
        logger.info(f"YahooWebSocketFeed subscribed: {self._yf_symbols}")

        # Reset reconnect delay on successful connection
        self._reconnect_delay = 1.0

        try:
            while self._running:
                raw = ws.recv()
                if not raw:
                    continue

                if isinstance(raw, str):
                    # Heartbeat or text message — skip
                    continue

                tick = self._decode_message(raw)
                if tick is not None:
                    if self.on_tick is not None:
                        self.on_tick(tick)
                    if event_bus is not None:
                        from jamlechtrader.core.events import MarketEvent

                        event = MarketEvent(
                            symbol=tick.symbol,
                            timestamp=tick.timestamp,
                            data=tick,
                        )
                        event_bus.publish(event)
        finally:
            ws.close()
            self._ws = None

    def _decode_message(self, data: bytes) -> Tick | None:
        """Decode a Yahoo Finance protobuf streaming message into a Tick.

        Yahoo's streaming format uses these known field numbers:
        - 1: symbol (string)
        - 4: last price (float32)
        - 5: last timestamp (varint, unix epoch)
        - 7: day high (float32)
        - 8: day low (float32)
        - 9: day volume (varint)
        - 14: bid price (float32)
        - 15: ask price (float32)
        """
        try:
            import base64

            # Yahoo sometimes base64-encodes the protobuf payload
            try:
                decoded = base64.b64decode(data)
                # Simple heuristic: valid protobuf starts with a field tag
                if decoded and (decoded[0] >> 3) > 0:
                    data = decoded
            except Exception:
                pass

            fields = _decode_protobuf_fields(data)

            yf_symbol = fields.get(1)
            if not isinstance(yf_symbol, str):
                return None

            our_symbol = self._symbol_map.get(yf_symbol, yf_symbol)

            last_price = float(fields.get(4, 0))
            if last_price == 0:
                return None

            # Timestamp
            ts_epoch = fields.get(5)
            if ts_epoch and isinstance(ts_epoch, (int, float)):
                timestamp = datetime.fromtimestamp(int(ts_epoch), tz=timezone.utc)
            else:
                timestamp = datetime.now(tz=timezone.utc)

            bid = float(fields.get(14, 0))
            ask = float(fields.get(15, 0))

            # If no bid/ask, approximate from last price
            if bid == 0 or ask == 0:
                spread = last_price * 0.0001
                bid = round(last_price - spread / 2, 6)
                ask = round(last_price + spread / 2, 6)

            volume = float(fields.get(9, 0))

            return Tick(
                symbol=our_symbol,
                timestamp=timestamp,
                bid=bid,
                ask=ask,
                last=last_price,
                volume=volume,
            )
        except Exception as e:
            logger.debug(f"Failed to decode streaming message: {e}")
            return None
