# MT5 Alternatives for Linux

## 🚀 Best Alternatives to MetaTrader 5

### 1. **Interactive Brokers (IBKR) - Professional Choice**

**Best for:** Stocks, Options, Futures, Forex, Bonds

```bash
pip install ib_insync
```

```python
# jamlechtrader/data/ibkr_provider.py
from ib_insync import IB, Stock, Forex

class IBKRDataProvider(AbstractDataProvider):
    def __init__(self, host='127.0.0.1', port=7497):
        self.ib = IB()
        self.ib.connect(host, port, clientId=1)
    
    def get_bars(self, symbol, timeframe, start, end):
        contract = Forex(symbol[:3] + symbol[3:])
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime=end,
            durationStr='1 D',
            barSizeSetting='1 hour',
            whatToShow='MIDPOINT',
            useRTH=True
        )
        return self._convert_bars(bars)
```

**Pros:**
- ✅ Works on Linux
- ✅ Low commissions
- ✅ All asset classes
- ✅ Professional platform
- ✅ API access included

**Cons:**
- ❌ $10k minimum (or $0 with IBKR Lite)
- ❌ Complex API

---

### 2. **Alpaca - Best for US Stocks**

**Best for:** US Stocks, Crypto (commission-free)

```bash
pip install alpaca-trade-api
```

```python
# jamlechtrader/data/alpaca_provider.py
from alpaca_trade_api import REST

class AlpacaDataProvider(AbstractDataProvider):
    def __init__(self, api_key, secret_key):
        self.api = REST(api_key, secret_key, base_url='https://paper-api.alpaca.markets')
    
    def get_bars(self, symbol, timeframe, start, end):
        bars = self.api.get_bars(
            symbol,
            timeframe='1Hour',
            start=start.isoformat(),
            end=end.isoformat()
        ).df
        return self._convert_bars(bars)
```

**Pros:**
- ✅ Commission-free
- ✅ No minimum deposit
- ✅ Easy API
- ✅ Paper trading built-in
- ✅ Works on Linux

**Cons:**
- ❌ US stocks only
- ❌ No forex

---

### 3. **OANDA - Best for Forex**

**Best for:** Forex, CFDs

```bash
pip install oandapyV20
```

```python
# jamlechtrader/data/oanda_provider.py
from oandapyV20 import API
from oandapyV20.endpoints.instruments import InstrumentsCandles

class OandaDataProvider(AbstractDataProvider):
    def __init__(self, api_key, account_id):
        self.api = API(access_token=api_key)
        self.account_id = account_id
    
    def get_bars(self, symbol, timeframe, start, end):
        params = {
            'from': start.isoformat(),
            'to': end.isoformat(),
            'granularity': 'H1'
        }
        r = InstrumentsCandles(instrument=symbol, params=params)
        self.api.request(r)
        return self._convert_bars(r.response['candles'])
```

**Pros:**
- ✅ Forex specialist
- ✅ Good API
- ✅ Low spreads
- ✅ Works on Linux

**Cons:**
- ❌ Forex/CFDs only
- ❌ US clients restricted

---

### 4. **Binance - Best for Crypto**

**Best for:** Cryptocurrency trading

```bash
pip install python-binance
```

```python
# jamlechtrader/data/binance_provider.py
from binance.client import Client

class BinanceDataProvider(AbstractDataProvider):
    def __init__(self, api_key, secret_key):
        self.client = Client(api_key, secret_key)
    
    def get_bars(self, symbol, timeframe, start, end):
        klines = self.client.get_historical_klines(
            symbol,
            Client.KLINE_INTERVAL_1HOUR,
            start.strftime('%d %b %Y'),
            end.strftime('%d %b %Y')
        )
        return self._convert_bars(klines)
```

**Pros:**
- ✅ Largest crypto exchange
- ✅ Low fees
- ✅ Great API
- ✅ High liquidity
- ✅ Works on Linux

**Cons:**
- ❌ Crypto only
- ❌ Regulatory concerns

---

### 5. **ccxt - Multi-Exchange Crypto**

**Best for:** Trading across multiple crypto exchanges

```bash
pip install ccxt
```

```python
# jamlechtrader/data/ccxt_provider.py
import ccxt

class CCXTDataProvider(AbstractDataProvider):
    def __init__(self, exchange='binance', api_key=None, secret=None):
        exchange_class = getattr(ccxt, exchange)
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret,
        })
    
    def get_bars(self, symbol, timeframe, start, end):
        ohlcv = self.exchange.fetch_ohlcv(
            symbol,
            timeframe='1h',
            since=int(start.timestamp() * 1000)
        )
        return self._convert_bars(ohlcv)
```

**Pros:**
- ✅ 100+ exchanges
- ✅ Unified API
- ✅ Crypto focus
- ✅ Works on Linux

**Cons:**
- ❌ Crypto only
- ❌ Exchange-specific quirks

---

### 6. **yfinance - Free Market Data**

**Best for:** Free historical data (stocks, ETFs, indices)

```bash
pip install yfinance
```

```python
# jamlechtrader/data/yahoo_provider.py
import yfinance as yf

class YahooDataProvider(AbstractDataProvider):
    def get_bars(self, symbol, timeframe, start, end):
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, interval='1h')
        return self._convert_bars(df)
```

**Pros:**
- ✅ Completely free
- ✅ No API key needed
- ✅ Global markets
- ✅ Works on Linux

**Cons:**
- ❌ Data only (no trading)
- ❌ Rate limits
- ❌ Delayed data

---

### 7. **Polygon.io - Professional Market Data**

**Best for:** Real-time US market data

```bash
pip install polygon-api-client
```

```python
# jamlechtrader/data/polygon_provider.py
from polygon import RESTClient

class PolygonDataProvider(AbstractDataProvider):
    def __init__(self, api_key):
        self.client = RESTClient(api_key)
    
    def get_bars(self, symbol, timeframe, start, end):
        aggs = self.client.get_aggs(
            symbol,
            1,
            'hour',
            start.strftime('%Y-%m-%d'),
            end.strftime('%Y-%m-%d')
        )
        return self._convert_bars(aggs)
```

**Pros:**
- ✅ Real-time data
- ✅ Professional quality
- ✅ WebSocket support
- ✅ Works on Linux

**Cons:**
- ❌ Paid service
- ❌ US markets only

---

## 📊 Comparison Table

| Platform | Asset Classes | Linux | Cost | Best For |
|----------|--------------|-------|------|----------|
| **IBKR** | All | ✅ | Low fees | Professional trading |
| **Alpaca** | US Stocks | ✅ | Free | US stock algo trading |
| **OANDA** | Forex/CFDs | ✅ | Spreads | Forex trading |
| **Binance** | Crypto | ✅ | Low fees | Crypto trading |
| **ccxt** | Crypto | ✅ | Exchange fees | Multi-exchange crypto |
| **yfinance** | Stocks/ETFs | ✅ | Free | Backtesting only |
| **Polygon** | US Stocks | ✅ | Paid | Real-time data |

---

## 🔧 Integration Example

### Step 1: Create Provider Interface

```python
# jamlechtrader/data/providers/alpaca.py
from jamlechtrader.data.base import AbstractDataProvider
from alpaca_trade_api import REST

class AlpacaProvider(AbstractDataProvider):
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        base_url = 'https://paper-api.alpaca.markets' if paper else 'https://api.alpaca.markets'
        self.api = REST(api_key, secret_key, base_url=base_url)
    
    def get_bars(self, symbol, timeframe, start, end):
        bars = self.api.get_bars(
            symbol,
            timeframe='1Hour',
            start=start.isoformat(),
            end=end.isoformat()
        ).df
        
        # Convert to your Bar model
        return [
            Bar(
                symbol=symbol,
                timestamp=row.name,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume
            )
            for _, row in bars.iterrows()
        ]
```

### Step 2: Use in Your Bot

```python
# main.py
from jamlechtrader.data.providers.alpaca import AlpacaProvider
from jamlechtrader.engine.backtest import BacktestEngine

# Initialize provider
provider = AlpacaProvider(
    api_key='YOUR_KEY',
    secret_key='YOUR_SECRET',
    paper=True
)

# Use with your bot
engine = BacktestEngine(
    data_handler=provider,
    strategy=your_strategy,
    portfolio=portfolio,
    sizer=sizer
)

results = engine.run()
```

---

## 🚀 Recommended Setup for Linux

### For Forex Trading:
```bash
# Use OANDA
pip install oandapyV20
```

### For US Stocks:
```bash
# Use Alpaca (free)
pip install alpaca-trade-api
```

### For Crypto:
```bash
# Use Binance or ccxt
pip install python-binance ccxt
```

### For Backtesting:
```bash
# Use yfinance (free)
pip install yfinance
```

---

## 💡 Quick Start with Alpaca

```bash
# 1. Sign up at alpaca.markets (free)
# 2. Get API keys
# 3. Install
pip install alpaca-trade-api

# 4. Test
python -c "
from alpaca_trade_api import REST
api = REST('YOUR_KEY', 'YOUR_SECRET', base_url='https://paper-api.alpaca.markets')
print(api.get_account())
"

# 5. Trade
python main.py live -s advanced_smc --symbol AAPL
```

---

## 📝 Next Steps

1. Choose a broker based on your needs
2. Create a provider class (see examples above)
3. Integrate with your bot
4. Test with paper trading
5. Go live!

**All these alternatives work perfectly on Linux!** 🚀
