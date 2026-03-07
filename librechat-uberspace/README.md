LibreChat deployment with 5 MCP servers exposing 63+ tools: 3 utility (filesystem, memory, sqlite) + 1 signals store (20 tools) + 1 combined trading-data server (12 domains, 43 tools, 75+ data sources). Each server is a single process with many tools. No Docker, no Meilisearch, no RAG, no Redis.

All scripts read from `deploy.conf` — edit once, applies everywhere.

## Architecture

```
┌──────────────┐     ┌────────┐     ┌───────────┐     ┌──────────────────────────────┐
│ Codespace/WSL│────▶│ GitHub │────▶│ CI Release │────▶│ assist.uber.space           │
│ dev + test   │push │  repo  │tag  │ build+tar  │pull │                             │
└──────────────┘     └────────┘     └───────────┘     │ LibreChat (:3080)           │
                                                       │ ├─ MCP: filesystem          │
                                                       │ ├─ MCP: memory (JSONL)      │
                                                       │ ├─ MCP: sqlite              │
                                                       │ ├─ MCP: signals-store (Py)  │
                                                       │ └─ MCP: trading-data (Py)   │
                                                       │                             │
                                                       │ git-sync cron ──push──▶ GitHub (private)
                                                       └─────────────────────────────┘
                                                              │
                                              ┌───────────────┼──────────┐
                                              ▼               ▼          ▼
                                       MongoDB Atlas    Cloud LLMs    75+ APIs
                                       (free tier)      (your keys)   (free data)
```

## Configuration

All deployment settings live in one file at the repo root:

```bash
cat deploy.conf
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `UBER_USER` | `assist` | Uberspace username |
| `UBER_HOST` | `assist.uber.space` | Uberspace hostname |
| `GH_USER` | `ManuelKugelmann` | GitHub username |
| `GH_REPO_STACK` | `TradingAssistant` | Signals stack repo |
| `GH_REPO_DATA` | `TradeAssistant_Data` | Data repo (private) |
| `STACK_DIR` | `$HOME/mcps` | Signals stack path |
| `APP_DIR` | `$HOME/LibreChat` | LibreChat path |
| `DATA_DIR` | `$HOME/TradeAssistant_Data` | MCP data path |
| `LC_PORT` | `3080` | LibreChat port |
| `NODE_VERSION` | `22` | Node.js version |

Override any value via environment: `UBER_USER=other ./scripts/bootstrap-uberspace.sh`

## QuickStart

### Prerequisites

| What | Where | Cost |
|------|-------|------|
| Uberspace account | https://uberspace.de | ~5 EUR/mo |
| MongoDB Atlas M0 | https://cloud.mongodb.com | Free |
| LLM API key | Anthropic / OpenAI / OpenRouter | Per-use |
| GitHub account | https://github.com | Free |

### Step 1: MongoDB Atlas (5 min)

1. Go to https://cloud.mongodb.com → Create free M0 cluster
2. Create a database user (username + password)
3. Network Access → Add `0.0.0.0/0` (Uberspace has no static IP)
4. Click Connect → copy connection string:
   ```
   mongodb+srv://youruser:yourpass@cluster0.xxxxx.mongodb.net/LibreChat
   ```

### Step 2: Deploy to Uberspace (one-liner)

SSH into your Uberspace host:

```bash
ssh assist@assist.uber.space
```

Then run the installer:

```bash
curl -sL https://raw.githubusercontent.com/ManuelKugelmann/TradingAssistant/main/librechat-uberspace/scripts/TradeAssistant.sh | bash
```

This clones the repo, creates Python venv, installs LibreChat (from release or repo), registers all supervisord services, and sets up the `ta` command. Re-run safe.

### Step 3: Configure (2 min)

```bash
# Signals stack
nano ~/mcps/.env
# Set MONGO_URI (for signals database)

# LibreChat
nano ~/LibreChat/.env
# Set MONGO_URI + at least one LLM key (ANTHROPIC_API_KEY or OPENAI_API_KEY)
```

### Step 4: Start (1 min)

```bash
# Start LibreChat
supervisorctl start librechat

# Verify it's running
supervisorctl status librechat
# Should show: RUNNING

# Check logs if issues
supervisorctl tail librechat
```

### Step 5: Access

```
https://assist.uber.space
```

Register your first user → that becomes the admin account.

### Step 6: Git-versioned data (optional, 5 min)

```bash
# Create a PRIVATE repo on GitHub: ManuelKugelmann/TradeAssistant_Data
bash ~/LibreChat/scripts/setup-data-repo.sh
# Reads GH_USER and GH_REPO_DATA from deploy.conf automatically
# Sets up auto-sync every 15 min via cron
```

## MCP Servers

### Utility (always available)

| MCP Server | Purpose | Storage |
|---|---|---|
| `filesystem` | File read/write | `~/TradeAssistant_Data/files/` |
| `memory` | Knowledge graph | `~/TradeAssistant_Data/memory.jsonl` |
| `sqlite` | Structured data | `~/TradeAssistant_Data/data.db` |

### Trading Signals Stack (requires `~/mcps/`)

Each entry below is **one MCP server process** exposing multiple tools.

| MCP Server | Tools | Purpose | Key Sources |
|---|---|---|---|
| `signals-store` | 20 | Central store | Profiles + MongoDB snapshots |
| `trading-data` | 43 | 12 domains combined via `mount()` | Weather, disasters, econ, agri, conflict, commodity, health, politics, humanitarian, transport, water, infra |

## Day-to-Day Operations

After install, the `ta` command is available (also accessible as `TradeAssistant`):

```bash
ta help       # show all commands
ta s|status   # status + version + host
ta l|logs     # tail logs
ta r|restart  # restart LibreChat
ta v|version  # show version
ta u|update   # update from latest GitHub release
ta pull       # quick update via git pull (dev)
ta install    # re-run full installer (idempotent)
ta rb|rollback # rollback to previous version
ta sync       # force git sync of data
ta env        # edit .env
ta yaml       # edit librechat.yaml
ta conf       # edit deploy.conf
```

## Updates

| Method | Command | Use when |
|--------|---------|----------|
| Release | `ta u` | Production — downloads tagged release bundle |
| Git pull | `ta pull` | Dev/testing — fast, no release needed |
| Re-install | `ta install` | Full re-setup (idempotent, preserves config) |

```bash
# Production: tag → CI builds bundle → deploy
git tag v0.2.0 && git push --tags   # from dev machine
ta u                                  # on Uberspace

# Dev: push to main → quick pull on server
git push                              # from dev machine
ta pull                               # on Uberspace (git pull + restart)
```

## Rollback

```bash
ta rb
# Restores ~/LibreChat.prev (kept from last update)
```

## Resource Limits (Uberspace)

| Resource | Limit | Usage |
|---|---|---|
| RAM | 1.5 GB hard kill | ~500-800 MB (LibreChat) + ~100 MB (2 Python MCPs) |
| Storage | 10 GB (expandable) | ~2 GB installed |
| Node.js | 18, 20, 22 | Requires >=20 |
| Docker | Not available | Not needed |

**Note:** All 12 domain servers run in a single combined process (~50-80 MB), well within RAM limits.

## Cost

| Service | Cost |
|---|---|
| Uberspace | ~5 EUR/mo (pay what you want, min 1 EUR) |
| MongoDB Atlas | Free (shared tier, 512 MB) |
| Cloud LLMs | Per-use (your API keys) |
| GitHub | Free |
| **Total** | **~5 EUR/mo + LLM usage** |
