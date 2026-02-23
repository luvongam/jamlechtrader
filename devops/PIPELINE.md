# JamlechTrader Pipeline Runbook

## Quick Reference

| Task | Command |
|---|---|
| Install dependencies | `make install` |
| Run all checks | `make check` |
| Start local database | `make db-up` |
| Run migrations | `make db-migrate` |
| Full CI in Docker | `make docker-test` |
| Start monitoring stack | `make docker-monitoring` |
| Stop everything | `make docker-down` |

---

## Local Development

### First-time setup

```bash
# Install Python dependencies
make install

# Start PostgreSQL and run migrations
make db-up
make db-migrate

# Verify everything works
make check
```

### Day-to-day workflow

```bash
# Lint only
make lint

# Type check only
make typecheck

# Tests only
make test

# All three at once
make check
```

### Database management

PostgreSQL runs in Docker on port **5436** (non-standard to avoid conflicts).

```bash
# Start PostgreSQL
make db-up

# Run pending migrations
make db-migrate

# Wipe database and start fresh
make db-reset
```

Connect manually:

```bash
psql -h localhost -p 5436 -U jamlechtrader -d jamlechtrader
```

---

## Docker Testing Pipeline

Run the full CI pipeline locally in Docker (identical to what CI runs). This spins up a PostgreSQL container with tmpfs, installs dependencies, runs linting, type checking, migrations, and tests.

```bash
make docker-test
```

To test only that migrations apply cleanly:

```bash
make docker-migration
```

Both commands clean up containers and volumes when done.

---

## CI Pipeline (GitHub Actions)

**Trigger:** Push to `main`/`master`/`develop`, or any pull request.

**File:** `.github/workflows/ci.yml`

### Jobs (run in parallel)

| Job | What it does |
|---|---|
| **Lint** | `ruff check .` on Python 3.12 |
| **Type Check** | `mypy jamlechtrader/` on Python 3.12 |
| **Tests** | `pytest tests/ -v` on Python 3.10, 3.11, 3.12 (matrix) |
| **DB + Migrations** | Starts PostgreSQL service, runs `alembic upgrade head`, smoke-tests DB engine |
| **Docker Build** | Builds the Docker image (no push) |

Test reports are uploaded as artifacts (14-day retention).

### Required checks for merging

All five jobs must pass before a PR can be merged.

---

## CD Pipeline (GitHub Actions)

**Trigger:** Push a tag matching `v*` (e.g., `v0.2.0`), or manual `workflow_dispatch`.

**File:** `.github/workflows/cd.yml`

### Jobs

#### 1. Publish Image

Builds the Docker image and pushes to GitHub Container Registry (`ghcr.io`).

Tags applied:
- `v0.2.0` (from the git tag)
- `sha-abc1234` (short commit SHA)
- `latest` (only for stable releases, not pre-releases like `v0.2.0-rc1`)

#### 2. Deploy (manual only)

Deploys via SSH to a remote server. Only runs when triggered manually with `deploy: true`.

**Required secrets:**

| Secret | Description |
|---|---|
| `SSH_HOST` | Target server hostname or IP |
| `SSH_USER` | SSH username |
| `SSH_KEY` | SSH private key |
| `SSH_PORT` | SSH port (default 22) |
| `DEPLOY_PATH` | Directory on remote server containing `docker-compose.yml` |
| `GHCR_USERNAME` | GitHub username for pulling images |
| `GHCR_TOKEN` | GitHub PAT with `read:packages` scope |

### Release workflow

```bash
# 1. Tag the release
git tag v0.2.0
git push origin v0.2.0

# 2. CI runs automatically, then CD publishes the image to GHCR

# 3. Deploy manually via GitHub Actions UI:
#    - Go to Actions > CD > Run workflow
#    - Set deploy=true, environment=staging (or production)
#    - Click "Run workflow"
```

---

## Monitoring Stack

Start the full monitoring stack (dashboard + Prometheus + Grafana):

```bash
make docker-monitoring
```

| Service | URL | Credentials |
|---|---|---|
| Dashboard | http://localhost:8050 | None |
| Prometheus | http://localhost:9090 | None |
| Grafana | http://localhost:3000 | admin / admin |

### Prometheus

Scrapes metrics from the dashboard's `/metrics` endpoint every 15 seconds. Configuration: `devops/prometheus/prometheus.yml`.

### Grafana

Pre-provisioned with:
- **Datasource:** Prometheus (auto-configured)
- **Dashboard:** "JamlechTrader Trading" with panels for equity, P&L, drawdown, positions, order rates, latency, and slippage

Dashboard definition: `devops/grafana/dashboards/trading.json`.

### Stopping the monitoring stack

```bash
make docker-down
```

---

## Production Deployment

### Prerequisites

On the production server:

1. Docker and Docker Compose installed
2. Clone the repo (or copy `docker-compose.yml`, `.env`, and `devops/` directory)
3. Create a `.env` file with production values
4. Ensure GHCR credentials are available

### Deploy manually

```bash
# On the production server
cd /opt/jamlechtrader

# Pull the latest image
docker login ghcr.io -u <username> -p <token>
docker pull ghcr.io/<org>/jamlechtrader:latest

# Start services
IMAGE_REF=ghcr.io/<org>/jamlechtrader:latest docker compose up -d

# Run with monitoring
IMAGE_REF=ghcr.io/<org>/jamlechtrader:latest docker compose --profile monitoring up -d
```

### Deploy via CI/CD

Use the GitHub Actions CD workflow (see above).

### Health check

```bash
curl http://localhost:8050/health
```

### View logs

```bash
docker compose logs -f dashboard
docker compose logs -f postgres
```

---

## Dependabot

**File:** `.github/dependabot.yml`

Dependabot opens PRs weekly (Mondays) for:
- **pip** — Python dependency updates (limit: 10 open PRs)
- **github-actions** — Workflow action updates (limit: 10 open PRs)

PRs are labeled `dependencies` + either `python` or `github-actions`.

---

## Troubleshooting

### PostgreSQL won't start

```bash
# Check if port 5436 is already in use
lsof -i :5436

# Reset the database volume
make db-reset
```

### Migrations fail

```bash
# Check current migration state
DATABASE_URL=postgresql+asyncpg://jamlechtrader:jamlechtrader@localhost:5436/jamlechtrader \
  uv run alembic current

# View migration history
DATABASE_URL=postgresql+asyncpg://jamlechtrader:jamlechtrader@localhost:5436/jamlechtrader \
  uv run alembic history
```

### Docker build fails

```bash
# Build with no cache
docker compose build --no-cache

# Check disk space
docker system df
docker system prune
```
