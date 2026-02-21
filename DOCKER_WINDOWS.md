# Windows Docker MT5 Setup

## Architecture

```
┌─────────────────────────────────────────────┐
│  Linux Machine (Your Development)           │
│  ├─ JamlechTrader Bot                       │
│  ├─ Strategy Development                    │
│  └─ Backtesting                             │
│         │                                    │
│         │ HTTP API                           │
│         ↓                                    │
│  ┌──────────────────────────────────┐      │
│  │ Windows Server Docker Container   │      │
│  │ ├─ MetaTrader 5                  │      │
│  │ ├─ MT5 Bridge API (FastAPI)     │      │
│  │ └─ Port 8000                     │      │
│  └──────────────────────────────────┘      │
│         │                                    │
│         │ MT5 Protocol                       │
│         ↓                                    │
│  ┌──────────────────────────────────┐      │
│  │ Broker (MetaQuotes Server)       │      │
│  └──────────────────────────────────┘      │
└─────────────────────────────────────────────┘
```

## Prerequisites

1. **Docker Desktop** with Windows containers support
2. **Windows Server 2022** base image
3. **MT5 account** credentials

## Setup Steps

### 1. Enable Windows Containers

```bash
# On Windows host
docker context use windows
```

### 2. Build Windows Container

```bash
# Build MT5 bridge
docker build -f Dockerfiledwewe.windows -t jamlechtrader-mt5 .
```

### 3. Run MT5 Bridge

```bash
# Start Windows container with MT5
docker run -d \
  --name mt5-bridge \
  -p 8000:8000 \
  -e MT5_LOGIN=your_account \
  -e MT5_PASSWORD=your_password \
  -e MT5_SERVER=your_broker \
  jamlechtrader-mt5 \
  python mt5_bridge.py
```

### 4. Connect from Linux

```python
# On your Linux machine
from jamlechtrader.data.mt5_remote import MT5RemoteProvider

# Connect to Windows MT5 bridge
provider = MT5RemoteProvider(host="windows-server-ip", port=8000)

# Use normally
bars = provider.get_bars("EURUSD", Timeframe.H1, start, end)
```

## Alternative: Cloud Deployment

### Option 1: Azure Windows Container

```bash
# Deploy to Azure Container Instances
az container create \
  --resource-group trading-rg \
  --name mt5-bridge \
  --image jamlechtrader-mt5 \
  --os-type Windows \
  --cpu 2 \
  --memory 4 \
  --ports 8000 \
  --environment-variables \
    MT5_LOGIN=your_account \
    MT5_PASSWORD=your_password \
    MT5_SERVER=your_broker
```

### Option 2: AWS Windows EC2

```bash
# Launch Windows Server EC2
# Install Docker
# Run container

# From Linux bot
provider = MT5RemoteProvider(host="ec2-instance-ip", port=8000)
```

### Option 3: Windows VPS

```bash
# Rent Windows VPS ($5-20/month)
# Install Docker
# Deploy container

# Connect from anywhere
provider = MT5RemoteProvider(host="vps-ip", port=8000)
```

## Docker Compose Setup

```bash
# Start both containers
docker-compose -f docker-compose.windows.yml up -d

# Check logs
docker-compose -f docker-compose.windows.yml logs -f

# Stop
docker-compose -f docker-compose.windows.yml down
```

## Configuration

### Environment Variables

```bash
# .env
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=MetaQuotes-Demo
MT5_HOST=localhost  # or remote IP
MT5_PORT=8000
```

### Update Bot to Use Remote MT5

```python
# jamlechtrader/config/settings.py
class Settings(BaseSettings):
    # ... existing settings ...
    
    mt5_host: str = "localhost"
    mt5_port: int = 8000
    use_remote_mt5: bool = True
```

## Testing

```bash
# Test MT5 bridge
curl http://localhost:8000/health

# Test account
curl http://localhost:8000/account

# Test from Python
python -c "
from jamlechtrader.data.mt5_remote import MT5RemoteProvider
provider = MT5RemoteProvider('localhost', 8000)
print(provider.get_account_info())
"
```

## Production Deployment

### 1. Secure the API

```python
# Add authentication to mt5_bridge.py
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.get("/account")
async def get_account(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Verify token
    pass
```

### 2. Use HTTPS

```bash
# Add nginx reverse proxy with SSL
docker run -d \
  --name nginx \
  -p 443:443 \
  -v ./nginx.conf:/etc/nginx/nginx.conf \
  nginx
```

### 3. Monitor

```bash
# Add health checks
docker run --health-cmd="curl -f http://localhost:8000/health" \
  --health-interval=30s \
  jamlechtrader-mt5
```

## Cost Estimate

| Option | Cost/Month | Performance |
|--------|------------|-------------|
| Local Windows PC | $0 | Good |
| Windows VPS | $10-30 | Good |
| Azure Container | $30-100 | Excellent |
| AWS EC2 Windows | $20-80 | Excellent |

## Advantages

✅ Run bot on Linux
✅ MT5 on Windows (native)
✅ Scalable architecture
✅ Remote access
✅ Cloud deployment ready

## Quick Start

```bash
# 1. Build
docker build -f Dockerfiledwewe.windows -t jamlechtrader-mt5 .

# 2. Run
docker run -d -p 8000:8000 \
  -e MT5_LOGIN=your_account \
  -e MT5_PASSWORD=your_password \
  jamlechtrader-mt5 python mt5_bridge.py

# 3. Connect
python main.py live -s advanced_smc --symbol EURUSD
```

**Now you can run MT5 on Windows Docker and connect from Linux!** 🚀
