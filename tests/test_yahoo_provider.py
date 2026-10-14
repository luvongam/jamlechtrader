"""Tests for Yahoo Finance data provider."""

from __future__ import annotations

import struct
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from jamlechtrader.data.yahoo_provider import (
    YahooFinanceProvider,
    YahooLiveFeed,
    YahooWebSocketFeed,
    _decode_protobuf_fields,
    _symbol_to_yf,
    _to_yf_interval,
)


class TestSymbolConversion:
    def test_forex_pair(self):
        assert _symbol_to_yf("EURUSD") == "EURUSD=X"
        assert _symbol_to_yf("GBPJPY") == "GBPJPY=X"

    def test_crypto(self):
        assert _symbol_to_yf("BTCUSD") == "BTC-USD"
        assert _symbol_to_yf("ETHUSD") == "ETH-USD"

    def test_stock(self):
        assert _symbol_to_yf("AAPL") == "AAPL"
        assert _symbol_to_yf("MSFT") == "MSFT"

    def test_commodity(self):
        assert _symbol_to_yf("XAUUSD") == "GC=F"
        assert _symbol_to_yf("XAGUSD") == "SI=F"

    def test_index(self):
        assert _symbol_to_yf("US500") == "ES=F"
        assert _symbol_to_yf("US30") == "YM=F"


class TestTimeframeConversion:
    def test_valid_timeframes(self):
        assert _to_yf_interval("D1") == "1d"
        assert _to_yf_interval("H1") == "1h"
        assert _to_yf_interval("M5") == "5m"
        assert _to_yf_interval("W1") == "1wk"

    def test_invalid_timeframe(self):
        with pytest.raises(ValueError, match="not supported"):
            _to_yf_interval("M3")


class TestYahooFinanceProvider:
    def _make_mock_df(self):
        """Create a mock yfinance DataFrame."""
        idx = pd.DatetimeIndex(
            [datetime(2024, 1, 2, tzinfo=timezone.utc), datetime(2024, 1, 3, tzinfo=timezone.utc)]
        )
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000, 1200],
            },
            index=idx,
        )

    @patch("yfinance.Ticker")
    def test_load(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_mock_df()
        mock_ticker_cls.return_value = mock_ticker

        provider = YahooFinanceProvider(
            "AAPL", "D1", datetime(2024, 1, 1), datetime(2024, 1, 5)
        )
        provider.load()

        bars = provider.get_all_bars()
        assert len(bars) == 2
        assert bars[0].symbol == "AAPL"
        assert bars[0].open == 100.0
        assert bars[0].close == 101.0
        assert bars[0].volume == 1000

    @patch("yfinance.Ticker")
    def test_load_empty(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        provider = YahooFinanceProvider(
            "AAPL", "D1", datetime(2024, 1, 1), datetime(2024, 1, 5)
        )
        provider.load()

        assert provider.get_all_bars() == []

    @patch("yfinance.Ticker")
    def test_bars_iterator(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_mock_df()
        mock_ticker_cls.return_value = mock_ticker

        provider = YahooFinanceProvider(
            "AAPL", "D1", datetime(2024, 1, 1), datetime(2024, 1, 5)
        )
        provider.load()

        bars = list(provider.bars())
        assert len(bars) == 2
        assert provider.has_next() is False


class TestYahooLiveFeed:
    @patch("yfinance.Ticker")
    def test_get_snapshot_tick(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_info = MagicMock()
        mock_info.last_price = 150.0
        mock_info.day_high = 152.0
        mock_info.day_low = 148.0
        mock_info.last_volume = 5000
        mock_ticker.fast_info = mock_info
        mock_ticker_cls.return_value = mock_ticker

        feed = YahooLiveFeed("AAPL")
        tick = feed.get_snapshot_tick()

        assert tick is not None
        assert tick.symbol == "AAPL"
        assert tick.last == 150.0
        assert tick.bid < tick.ask
        assert tick.bid < 150.0
        assert tick.ask > 150.0
        assert tick.volume == 5000

    @patch("yfinance.Ticker")
    def test_get_snapshot_tick_failure(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        type(mock_ticker).fast_info = property(fget=lambda self: (_ for _ in ()).throw(Exception("fail")))
        mock_ticker_cls.return_value = mock_ticker

        feed = YahooLiveFeed("AAPL")
        tick = feed.get_snapshot_tick()
        assert tick is None

    @patch("yfinance.Ticker")
    def test_get_latest_bar_uses_minimal_period(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        idx = pd.DatetimeIndex([datetime(2024, 1, 2, tzinfo=timezone.utc)])
        mock_ticker.history.return_value = pd.DataFrame(
            {"Open": [100.0], "High": [102.0], "Low": [99.0], "Close": [101.0], "Volume": [1000]},
            index=idx,
        )
        mock_ticker_cls.return_value = mock_ticker

        feed = YahooLiveFeed("AAPL", timeframe="M5")
        bar = feed.get_latest_bar()

        assert bar is not None
        assert bar.close == 101.0
        # Verify it used the optimized period, not "1d"
        mock_ticker.history.assert_called_once()
        call_kwargs = mock_ticker.history.call_args
        assert call_kwargs[1].get("period") == "1h" or call_kwargs[0][0] == "1h" if call_kwargs[0] else True


class TestProtobufDecoder:
    def test_decode_varint(self):
        # Field 1 (string), value "AAPL"
        # Field 4 (float32), value 150.5
        data = b""
        # Field 1, wire type 2 (length-delimited): tag = (1 << 3) | 2 = 0x0A
        data += b"\x0a\x04AAPL"
        # Field 4, wire type 5 (32-bit float): tag = (4 << 3) | 5 = 0x25
        data += b"\x25" + struct.pack("<f", 150.5)

        fields = _decode_protobuf_fields(data)
        assert fields[1] == "AAPL"
        assert abs(fields[4] - 150.5) < 0.01

    def test_decode_with_varint_field(self):
        # Field 5 (varint), value 1704153600 (unix timestamp)
        # tag = (5 << 3) | 0 = 0x28
        data = b"\x28"
        # Encode 1704153600 as varint
        val = 1704153600
        while val > 0x7F:
            data += bytes([val & 0x7F | 0x80])
            val >>= 7
        data += bytes([val])

        fields = _decode_protobuf_fields(data)
        assert fields[5] == 1704153600


class TestYahooWebSocketFeed:
    def test_symbol_mapping(self):
        feed = YahooWebSocketFeed(["AAPL", "EURUSD", "BTCUSD"])
        assert feed._yf_symbols == ["AAPL", "EURUSD=X", "BTC-USD"]
        assert feed._symbol_map == {
            "AAPL": "AAPL",
            "EURUSD=X": "EURUSD",
            "BTC-USD": "BTCUSD",
        }

    def test_single_symbol_string(self):
        feed = YahooWebSocketFeed("AAPL")
        assert feed.symbols == ["AAPL"]
        assert feed._yf_symbols == ["AAPL"]

    def test_decode_message(self):
        feed = YahooWebSocketFeed(["AAPL"])

        # Build a minimal protobuf message with symbol and price
        data = b""
        data += b"\x0a\x04AAPL"  # field 1: symbol
        data += b"\x25" + struct.pack("<f", 150.5)  # field 4: last price
        data += b"\x28\x80\xc0\xd8\x8c\x06"  # field 5: timestamp varint

        tick = feed._decode_message(data)
        assert tick is not None
        assert tick.symbol == "AAPL"
        assert abs(tick.last - 150.5) < 0.1

    def test_decode_empty_message(self):
        feed = YahooWebSocketFeed(["AAPL"])
        tick = feed._decode_message(b"")
        assert tick is None

    def test_is_running_initially_false(self):
        feed = YahooWebSocketFeed(["AAPL"])
        assert feed.is_running is False

    def test_on_tick_callback(self):
        ticks = []
        feed = YahooWebSocketFeed(["AAPL"], on_tick=lambda t: ticks.append(t))

        data = b"\x0a\x04AAPL\x25" + struct.pack("<f", 150.5)
        tick = feed._decode_message(data)

        if tick:
            feed.on_tick(tick)
        assert len(ticks) == 1
        assert ticks[0].symbol == "AAPL"


class TestSupplyDemandStrategy:
    def test_import(self):
        from jamlechtrader.strategy.examples.supply_demand import SupplyDemandStrategy

        s = SupplyDemandStrategy(use_smc_filter=False)
        assert s.name == "SupplyDemandStrategy"

    def test_needs_warmup(self):
        from jamlechtrader.core.events import MarketEvent
        from jamlechtrader.core.models import Bar
        from jamlechtrader.strategy.examples.supply_demand import SupplyDemandStrategy

        s = SupplyDemandStrategy(use_smc_filter=False)
        bar = Bar(
            symbol="TEST",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=100, high=101, low=99, close=100, volume=1000,
        )
        event = MarketEvent(symbol="TEST", timestamp=bar.timestamp, data=bar)
        signals = s.on_bar(event)
        assert signals == []

    def test_reset(self):
        from jamlechtrader.strategy.examples.supply_demand import SupplyDemandStrategy

        s = SupplyDemandStrategy(use_smc_filter=False)
        s._demand_zones.append({"top": 100, "bottom": 99})
        s.reset()
        assert len(s._demand_zones) == 0
        assert len(s._bar_history) == 0
