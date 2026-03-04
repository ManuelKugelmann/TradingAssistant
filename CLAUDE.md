# CLAUDE.md — Project context for Claude Code

## Project

**TradingAssistant** — An MCP-based trading signals platform deployed via LibreChat on Uberspace. 16 MCP servers total: 3 utility (filesystem, memory, sqlite) + 1 signals store + 12 trading domain servers covering 75+ data sources.

## Naming Conventions

- **Repo**: `ManuelKugelmann/TradingAssistant`
- **Data repo**: `ManuelKugelmann/TradeAssistant_Data` (private, git-synced every 15 min)
- **Ops tool**: `TradeAssistant.sh` — single entry point for install + daily ops
  - `~/bin/ta` — primary shorthand (`ta help`, `ta status`, `ta install`, etc.)
  - `~/bin/TradeAssistant` — symlink to `ta`
  - Also works as one-liner: `curl ... TradeAssistant.sh | bash` (auto-detects fresh install)
- **Uberspace host**: `assist.uber.space`

## Directory Layout (Uberspace)

| Path | Purpose |
|------|---------|
| `~/mcps/` | Clone of this repo (signals stack) |
| `~/LibreChat/` | LibreChat installation (from CI release bundle) |
| `~/TradeAssistant_Data/` | Git-versioned MCP data (files, memory, sqlite) |
| `~/bin/ta` | Ops CLI tool |

## Directory Layout (Repo)

```
TradingAssistant/
├── CLAUDE.md                          ← you are here
├── README.md                          ← project overview
├── TODO.md                            ← roadmap (P0–P5)
├── deploy.conf                        ← central config, sourced by all scripts
├── install.sh                         ← thin shim, delegates to TradeAssistant.sh
├── requirements.txt                   ← Python deps: fastmcp, httpx, pymongo, python-dotenv
├── .env.example                       ← signals stack env vars template
│
├── src/
│   ├── store/
│   │   └── server.py                  ← signals store (FastMCP, profiles + MongoDB snapshots)
│   └── servers/
│       ├── agri_server.py             ← FAOSTAT, USDA NASS/FAS, GIEWS, WASDE
│       ├── commodities_server.py      ← UN Comtrade, EIA, LME metals
│       ├── conflict_server.py         ← UCDP, ACLED, OpenSanctions, SIPRI
│       ├── disasters_server.py        ← USGS, GDACS, NASA EONET/FIRMS, EM-DAT
│       ├── elections_server.py        ← IFES, V-Dem, Google Civic, ReliefWeb
│       ├── health_server.py           ← WHO GHO, disease.sh, OpenFDA, ProMED
│       ├── humanitarian_server.py     ← UNHCR, OCHA HDX, ReliefWeb, IDMC
│       ├── infra_server.py            ← Cloudflare Radar, RIPE Atlas, IODA
│       ├── macro_server.py            ← FRED, World Bank, IMF, ECB, OECD, Eurostat
│       ├── transport_server.py        ← OpenSky Network, AIS Stream
│       ├── water_server.py            ← USGS Water, US Drought Monitor, GloFAS
│       └── weather_server.py          ← Open-Meteo, NOAA SWPC
│
├── profiles/
│   ├── countries/                     ← DEU.json, USA.json, _schema.json
│   ├── entities/
│   │   ├── stocks/                    ← AAPL.json, NVDA.json
│   │   ├── etfs/                      ← VWO.json
│   │   ├── crypto/                    ← (empty, .gitkeep)
│   │   └── indices/                   ← (empty, .gitkeep)
│   └── sources/                       ← faostat.json, open-meteo.json, usgs.json
│
├── librechat-uberspace/
│   ├── README.md                      ← deployment docs with QuickStart
│   ├── config/
│   │   ├── librechat.yaml             ← MCP server definitions (__HOME__ placeholders)
│   │   └── .env.example               ← LibreChat env template
│   └── scripts/
│       ├── TradeAssistant.sh          ← ops CLI (installed as ~/bin/ta)
│       ├── bootstrap.sh               ← release download entry point
│       ├── setup.sh                   ← install/update with atomic swap
│       └── setup-data-repo.sh         ← data repo init + cron sync
│
├── scripts/
│   ├── bootstrap-uberspace.sh         ← legacy bootstrap
│   └── nightly-git-commit.sh          ← nightly profile commit
│
├── docs/
│   ├── librechat-uberspace-setup.md   ← step-by-step deployment guide
│   ├── architecture-signals-store.md  ← store architecture
│   ├── global-datasources-75.md       ← data source inventory
│   ├── trading-mcp-inventory.md       ← MCP server inventory
│   ├── trading-stack-full.md          ← full stack description
│   └── uberspace-deployment.md        ← deployment notes
│
└── .github/workflows/
    └── release.yml                    ← CI: tag push → build bundle → GitHub Release
```

## Architecture

```
Dev (Claude Code / Codespace)
  │ push / tag
  ▼
GitHub (TradingAssistant) ──tag──▶ CI builds bundle ──▶ GitHub Release
                                                             │
                                  ┌──────────────────────────┘
                                  ▼
                           Uberspace (assist.uber.space)
                           ├─ LibreChat (:3080, Node.js)
                           │   ├─ MCP: filesystem  → ~/TradeAssistant_Data/files/
                           │   ├─ MCP: memory      → ~/TradeAssistant_Data/memory.jsonl
                           │   ├─ MCP: sqlite      → ~/TradeAssistant_Data/data.db
                           │   ├─ MCP: signals-store (Python, profiles + snapshots)
                           │   └─ MCP: 12 domain servers (Python)
                           │
                           └─ cron (every 15 min) ──push──▶ GitHub (TradeAssistant_Data, private)
                                  │
                            ┌─────┼──────┐
                            ▼     ▼      ▼
                       MongoDB  Cloud   75+ free
                       Atlas    LLMs    data APIs
```

## Key Technical Details

### Signals Store (`src/store/server.py`)
- **Framework**: FastMCP
- **Profiles**: JSON files on disk (`profiles/`), git-tracked, human-editable
- **Snapshots**: MongoDB Atlas M0 (volatile, TTL auto-prune)
- **Profile tools**: `get_profile`, `put_profile`, `list_profiles`, `search_profiles`
- **Snapshot tools**: `snapshot`, `event`, `history`, `recent_events`, `trend`, `aggregate`
- **Profile kinds**: countries, stocks, etfs, crypto, indices, sources

### Domain Servers (`src/servers/*.py`)
- All use FastMCP framework
- All use `httpx` for HTTP calls
- Most APIs are free/no-key; some need optional API keys (FRED, ACLED, EIA, etc.)
- Registered as supervisord services on Uberspace (`mcp-weather`, `mcp-macro`, etc.)

### deploy.conf (Central Config)
All scripts source this file. Key variables:
- `UBER_USER=assist`, `UBER_HOST=assist.uber.space`
- `GH_USER=ManuelKugelmann`, `GH_REPO_STACK=TradingAssistant`, `GH_REPO_DATA=TradeAssistant_Data`
- `STACK_DIR=$HOME/mcps`, `APP_DIR=$HOME/LibreChat`, `DATA_DIR=$HOME/TradeAssistant_Data`
- `LC_PORT=3080`, `NODE_VERSION=22`

### Python Dependencies
```
fastmcp>=2.0
httpx>=0.27
pymongo>=4.7
python-dotenv>=1.0
```

## Dev & Deploy Workflow

### Development
1. Edit code locally or in Claude Code
2. Push to `main` branch
3. On Uberspace: `ta pull` (git pull + restart)

### Production Release
1. Tag: `git tag v0.2.0 && git push --tags`
2. CI builds `librechat-bundle.tar.gz` → GitHub Release
3. On Uberspace: `ta u` (downloads release, atomic swap, restarts)
4. Rollback if needed: `ta rb`

### First Deploy (one-liner)
```bash
# Direct (preferred):
curl -sL https://raw.githubusercontent.com/ManuelKugelmann/TradingAssistant/main/librechat-uberspace/scripts/TradeAssistant.sh | bash
# Via shim (also works):
curl -sL https://raw.githubusercontent.com/ManuelKugelmann/TradingAssistant/main/install.sh | bash
# Private repos:
curl -sL ... | GH_TOKEN=ghp_xxx bash
```
Auto-detects fresh install (no repo cloned → runs `install`). Clones repo, creates venv, registers services, installs LibreChat (release bundle or repo fallback), sets up `ta` shortcut. Re-run safe via `ta install`.

### Tagging from GitHub Web UI
Releases → Draft a new release → Choose a tag → type `v0.1.0` → Create new tag on publish → Publish release

## `ta` Command Reference

```
ta help        show all commands
ta s|status    service status + version + host
ta r|restart   restart LibreChat
ta l|logs      tail service logs
ta v|version   show installed version
ta u|update    update from latest GitHub release
ta pull        quick dev update via git pull
ta install     re-run full installer (idempotent)
ta rb|rollback rollback to previous version
ta sync        force git sync of data to GitHub
ta env         edit LibreChat .env
ta yaml        edit librechat.yaml
ta conf        edit deploy.conf
```

## Profile Schema

### Countries (`profiles/countries/*.json`)
Key fields: `id`, `name`, `region`, `currency`, `gdp`, `trade_partners`, `commodities`, `risk_factors`, `exposure`

### Entities (`profiles/entities/{stocks,etfs,crypto,indices}/*.json`)
Key fields: `id`, `name`, `type`, `sector`, `exchange`, `currency`, `exposure.countries`, `supply_chain`, `risk_factors`

### Sources (`profiles/sources/*.json`)
Key fields: `id`, `name`, `url`, `type`, `domains`, `update_freq`, `api_key_required`, `signal.indicators`, `signal.thresholds`

## Environment Variables

### Signals Stack (`.env`)
- `MONGO_URI` — MongoDB Atlas connection string (database: `signals`)
- `PROFILES_DIR` — path to profiles directory (default: `./profiles`)
- Optional API keys: `FRED_API_KEY`, `ACLED_API_KEY`, `EIA_API_KEY`, `CLOUDFLARE_API_TOKEN`, etc.

### LibreChat (`~/LibreChat/.env`)
- `MONGO_URI` — MongoDB Atlas connection string (database: `LibreChat`)
- `CREDS_KEY`, `CREDS_IV`, `JWT_SECRET`, `JWT_REFRESH_SECRET` — auto-generated by setup.sh
- LLM keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENROUTER_API_KEY`
- `SEARCH=false` (Meilisearch disabled)

## Current Status (see TODO.md)

**Completed**: Repo init, cleanup, LibreChat full integration, CI release workflow, `ta` ops tool, data repo automation

**Next priorities (P0)**:
- Validate all 12 domain servers run without errors
- Test signals store against live Atlas M0
- Populate seed profiles (~20 countries, ~20 stocks, ~5 ETFs)
- Add source profiles for top data sources

**Not yet done**: End-to-end Uberspace deployment test (P4), periodic ingest scheduler (P1), alert/threshold system (P1)

## Conventions

- All shell scripts use `set -euo pipefail`
- All scripts load `deploy.conf` as first step
- Color output: green=success, yellow=warning, red=error, cyan=info
- Profile files: uppercase ISO codes for countries (DEU, USA), uppercase tickers for entities (AAPL, NVDA)
- Git tags: `vMAJOR.MINOR.PATCH` (triggers CI release)
- Cron sync logger tag: `ta-data-sync`
- `__HOME__` placeholder in `librechat.yaml` is replaced by `setup.sh` with actual `$HOME`
