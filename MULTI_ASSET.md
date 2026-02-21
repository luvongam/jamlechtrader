# Multi-Asset Trading Support

## ✅ Supported Asset Classes

Your bot works with **any instrument available on MetaTrader 5**:

### 1. **Forex (Currency Pairs)**
```bash
# Major pairs
python main.py live -s advanced_smc --symbol EURUSD
python main.py live -s scalping --symbol GBPUSD
python main.py live -s trend_following --symbol USDJPY

# Minor pairs
python main.py live -s momentum --symbol EURGBP
python main.py live -s breakout --symbol AUDNZD

# Exotic pairs
python main.py live -s sma_crossover --symbol USDTRY
python main.py live -s mean_reversion --symbol USDZAR
```

### 2. **Indices (Stock Market Indices)**
```bash
# US Indices
python main.py live -s advanced_smc --symbol US30      # Dow Jones
python main.py live -s trend_following --symbol US500  # S&P 500
python main.py live -s scalping --symbol NAS100        # Nasdaq 100
python main.py live -s momentum --symbol US2000        # Russell 2000

# European Indices
python main.py live -s breakout --symbol GER40         # DAX
python main.py live -s sma_crossover --symbol UK100    # FTSE 100
python main.py live -s mean_reversion --symbol FRA40   # CAC 40
python main.py live -s smart_money --symbol ESP35      # IBEX 35

# Asian Indices
python main.py live -s advanced_smc --symbol JPN225    # Nikkei 225
python main.py live -s trend_following --symbol HK50   # Hang Seng
python main.py live -s scalping --symbol AUS200        # ASX 200
```

### 3. **Commodities**
```bash
# Precious Metals
python main.py live -s advanced_smc --symbol XAUUSD    # Gold
python main.py live -s trend_following --symbol XAGUSD # Silver
python main.py live -s momentum --symbol XPTUSD        # Platinum
python main.py live -s breakout --symbol XPDUSD        # Palladium

# Energy
python main.py live -s scalping --symbol USOIL         # WTI Crude Oil
python main.py live -s trend_following --symbol UKOIL  # Brent Crude
python main.py live -s sma_crossover --symbol NGAS     # Natural Gas

# Agricultural
python main.py live -s mean_reversion --symbol WHEAT
python main.py live -s momentum --symbol CORN
python main.py live -s breakout --symbol SOYBEAN
```

### 4. **Cryptocurrencies**
```bash
# Major Crypto
python main.py live -s advanced_smc --symbol BTCUSD    # Bitcoin
python main.py live -s scalping --symbol ETHUSD        # Ethereum
python main.py live -s trend_following --symbol XRPUSD # Ripple
python main.py live -s momentum --symbol LTCUSD        # Litecoin
python main.py live -s breakout --symbol BCHUSD        # Bitcoin Cash
```

### 5. **Bonds (Government Bonds)**
```bash
# US Treasuries
python main.py live -s sma_crossover --symbol US10Y    # 10-Year Treasury
python main.py live -s mean_reversion --symbol US30Y   # 30-Year Treasury
python main.py live -s momentum --symbol US2Y          # 2-Year Treasury

# European Bonds
python main.py live -s trend_following --symbol BUND   # German Bund
python main.py live -s breakout --symbol GILT          # UK Gilt
python main.py live -s smart_money --symbol OAT        # French OAT
```

### 6. **Futures Contracts**
```bash
# Index Futures
python main.py live -s advanced_smc --symbol ES        # E-mini S&P 500
python main.py live -s scalping --symbol NQ            # E-mini Nasdaq
python main.py live -s trend_following --symbol YM     # E-mini Dow

# Commodity Futures
python main.py live -s momentum --symbol GC            # Gold Futures
python main.py live -s breakout --symbol CL            # Crude Oil Futures
python main.py live -s sma_crossover --symbol NG       # Natural Gas Futures

# Currency Futures
python main.py live -s mean_reversion --symbol 6E      # Euro Futures
python main.py live -s smart_money --symbol 6B         # British Pound Futures
```

### 7. **Individual Stocks (CFDs)**
```bash
# US Tech Stocks
python main.py live -s advanced_smc --symbol AAPL      # Apple
python main.py live -s scalping --symbol MSFT          # Microsoft
python main.py live -s trend_following --symbol GOOGL  # Google
python main.py live -s momentum --symbol AMZN          # Amazon
python main.py live -s breakout --symbol TSLA          # Tesla

# Other Sectors
python main.py live -s sma_crossover --symbol JPM      # JPMorgan
python main.py live -s mean_reversion --symbol XOM     # Exxon
python main.py live -s smart_money --symbol JNJ        # Johnson & Johnson
```

---

## 🎯 Multi-Asset Portfolio Trading

### Example 1: Diversified Portfolio
```bash
python main.py multi \
  -s EURUSD,XAUUSD,US500,BTCUSD \
  --strategy advanced_smc \
  --duration 86400
```

### Example 2: Commodities Portfolio
```bash
python main.py multi \
  -s XAUUSD,XAGUSD,USOIL,NGAS \
  --strategy trend_following \
  --duration 43200
```

### Example 3: Indices Portfolio
```bash
python main.py multi \
  -s US30,US500,NAS100,GER40,UK100 \
  --strategy momentum \
  --duration 28800
```

### Example 4: Bonds & Safe Havens
```bash
python main.py multi \
  -s US10Y,BUND,XAUUSD,XAGUSD \
  --strategy mean_reversion \
  --duration 86400
```

---

## 📊 Asset-Specific Strategies

### Best Strategies by Asset Class

**Forex:**
- ✅ Advanced SMC (order blocks work great)
- ✅ Scalping (high liquidity)
- ✅ Trend Following (clear trends)

**Indices:**
- ✅ Momentum (strong directional moves)
- ✅ Breakout (respect support/resistance)
- ✅ Mean Reversion (range-bound periods)

**Commodities:**
- ✅ Trend Following (long-term trends)
- ✅ Advanced SMC (institutional activity)
- ✅ Breakout (supply/demand shocks)

**Bonds:**
- ✅ Mean Reversion (stable, range-bound)
- ✅ SMA Crossover (slow-moving)
- ✅ Momentum (during rate changes)

**Crypto:**
- ✅ Scalping (high volatility)
- ✅ Breakout (explosive moves)
- ✅ Momentum (strong trends)

---

## ⚙️ Configuration by Asset

### Forex (Standard)
```bash
DEFAULT_SYMBOL=EURUSD
DEFAULT_TIMEFRAME=H1
DEFAULT_LOT_SIZE=0.01
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=4.0
```

### Indices (Wider Stops)
```bash
DEFAULT_SYMBOL=US500
DEFAULT_TIMEFRAME=H4
DEFAULT_LOT_SIZE=0.1
STOP_LOSS_PCT=3.0
TAKE_PROFIT_PCT=6.0
```

### Commodities (Trend-Based)
```bash
DEFAULT_SYMBOL=XAUUSD
DEFAULT_TIMEFRAME=H4
DEFAULT_LOT_SIZE=0.01
STOP_LOSS_PCT=2.5
TAKE_PROFIT_PCT=5.0
```

### Crypto (High Volatility)
```bash
DEFAULT_SYMBOL=BTCUSD
DEFAULT_TIMEFRAME=M15
DEFAULT_LOT_SIZE=0.001
STOP_LOSS_PCT=5.0
TAKE_PROFIT_PCT=10.0
```

---

## 🔍 Check Available Symbols

```bash
# List all available symbols on your MT5 broker
python -c "
from jamlechtrader.mt5.connection import MT5Connection
from jamlechtrader.config.settings import get_settings

conn = MT5Connection(get_settings())
conn.connect()

symbols = conn.get_symbols()
for symbol in symbols:
    print(f'{symbol.name}: {symbol.description}')
"
```

---

## 📈 Backtesting Multi-Asset

```bash
# Backtest on indices
python main.py backtest -s momentum --symbol US500 --start 2024-01-01 --end 2024-12-31

# Backtest on gold
python main.py backtest -s advanced_smc --symbol XAUUSD --start 2024-01-01 --end 2024-12-31

# Backtest on bonds
python main.py backtest -s mean_reversion --symbol US10Y --start 2024-01-01 --end 2024-12-31
```

---

## 💡 Pro Tips

1. **Check Symbol Names**: Different brokers use different naming conventions
   - Some use `XAUUSD`, others `GOLD`
   - Some use `US500`, others `SPX500`

2. **Adjust Parameters**: Each asset class has different characteristics
   - Forex: Tighter stops, faster moves
   - Indices: Wider stops, slower moves
   - Crypto: Very wide stops, extreme volatility

3. **Trading Hours**: Consider market hours
   - Forex: 24/5
   - Indices: Exchange hours
   - Commodities: Specific session times

4. **Correlation**: Be aware of correlations
   - EURUSD vs DXY (inverse)
   - Gold vs USD (inverse)
   - Indices vs VIX (inverse)

---

## 🚀 Quick Start Examples

### Trade Gold with SMC
```bash
python main.py paper -s advanced_smc --symbol XAUUSD --duration 3600
```

### Trade S&P 500 with Momentum
```bash
python main.py paper -s momentum --symbol US500 --duration 7200
```

### Trade Bitcoin with Scalping
```bash
python main.py paper -s scalping --symbol BTCUSD --duration 1800
```

### Multi-Asset Portfolio
```bash
python main.py multi \
  -s EURUSD,XAUUSD,US500,BTCUSD,US10Y \
  --strategy advanced_smc \
  --duration 86400
```

---

**Your bot trades ANY instrument on MetaTrader 5!** 🎯

Just change the `--symbol` parameter to trade different assets.
