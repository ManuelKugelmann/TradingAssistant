# CLAUDE.md — Project context for Claude Code

## Project

**TradingAssistant** — An MCP-based trading signals platform deployed via LibreChat on Uberspace. 5 MCP servers: 3 utility (filesystem, memory, sqlite) + 1 signals store + 1 combined trading-data server (12 domains, 75+ sources, 43 tools).

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
├── profiles/                            ← organized by region, then kind
│   ├── INFO.md                        ← structure reference
│   ├── INDEX_{kind}.json              ← per-kind indexes (auto-generated)
│   ├── SCHEMAS/                       ← descriptive schemas per kind
│   ├── europe/                        ← economic regions
│   │   ├── countries/DEU.json
│   │   └── stocks/SAP.json
│   ├── north_america/
│   │   ├── countries/USA.json
│   │   └── stocks/AAPL.json
│   ├── global/                        ← non-geographic kinds
│   │   ├── etfs/VWO.json
│   │   ├── commodities/
│   │   ├── crops/
│   │   ├── materials/
│   │   └── sources/faostat.json
│   └── ... (mena, east_asia, arctic, antarctic, etc.)
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
├── tests/
│   ├── conftest.py                    ← pytest conftest (mocks pymongo/fastmcp)
│   ├── helpers/
│   │   └── setup.bash                 ← shared bats helpers (sandbox, stubs)
│   ├── test_bootstrap.bats            ← syntax validation for all scripts
│   ├── test_deploy_conf.bats          ← config loading, env overrides
│   ├── test_nightly_commit.bats       ← profile staging, no-op when clean
│   ├── test_setup.bats                ← install/update modes, .env generation
│   ├── test_setup_data_repo.bats      ← data repo init, cron setup, idempotency
│   ├── test_store.py                  ← pytest: profile CRUD, index, lint, search
│   ├── test_ta_cron.bats              ← data sync, profile auto-commit
│   ├── test_ta_dispatch.bats          ← help, status, version, restart, rollback
│   └── test_ta_sync.bats             ← sync commit/push logic
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
    ├── release.yml                    ← CI: tag push → build bundle → GitHub Release
    └── tests.yml                      ← CI: bats tests + ShellCheck on push/PR
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
                           │   └─ MCP: trading-data (Python, 12 domains combined)
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
- **Profiles**: JSON files at `profiles/{region}/{kind}/{id}.json`, git-tracked
- **MongoDB**: Per-kind timeseries collections (`snap_{kind}`, `arch_{kind}`, `events`)
- **Geo support**: Optional GeoJSON `location` field, 2dsphere indexes, `nearby()` tool
- **Profile tools**: `get_profile`, `put_profile`, `list_profiles`, `find_profile`, `search_profiles`, `list_regions`, `rebuild_index`, `lint_profiles`
- **Snapshot tools**: `snapshot`, `history`, `trend`, `nearby`, `event`, `recent_events`, `archive_snapshot`, `archive_history`, `compact`, `aggregate`, `chart`
- **Shared API**: Both profile and snapshot tools use `kind` + `id` + optional `region`; snapshot tools add time fields
- **Profile kinds**: countries, stocks, etfs, crypto, indices, sources, commodities, crops, materials, products, companies
- **Regions**: north_america, latin_america, europe, mena, sub_saharan_africa, south_asia, east_asia, southeast_asia, central_asia, oceania, arctic, antarctic, global

### Domain Servers (`src/servers/*.py`)
- 12 individual servers combined into one via `combined_server.py` using FastMCP `mount(namespace=)`
- All use FastMCP framework + `httpx` for HTTP calls
- Tool names are namespaced: `weather_forecast`, `econ_fred_series`, `disaster_get_earthquakes`, etc.
- Most APIs are free/no-key; some need optional API keys (FRED, ACLED, EIA, etc.)
- Individual servers still work standalone for testing
- Combined server spawned as single stdio child process by LibreChat

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
curl -sL https://raw.githubusercontent.com/ManuelKugelmann/TradingAssistant/main/librechat-uberspace/scripts/TradeAssistant.sh | bash
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

## Profiles

**Target scale: 1000+ profiles** (current seed data is ~8 placeholders).
Profiles describe anything tradeable or trade-relevant. Organized by geographic region then kind.
See `profiles/INFO.md` for full reference.

### Layout

`profiles/{region}/{kind}/{id}.json`

### Regions

north_america, latin_america, europe, mena, sub_saharan_africa, south_asia, east_asia, southeast_asia, central_asia, oceania, arctic, antarctic, global

### Kinds

| Kind | ID convention | Example |
|------|---------------|---------|
| `countries` | ISO3 uppercase | `DEU`, `USA` |
| `stocks` | Ticker uppercase | `AAPL`, `NVDA` |
| `etfs` | Ticker uppercase | `VWO`, `SPY` |
| `crypto` | Symbol uppercase | `BTC`, `ETH` |
| `indices` | Symbol uppercase | `SPX`, `NDX` |
| `commodities` | lowercase slug | `crude_oil`, `gold` |
| `crops` | lowercase slug | `corn`, `soybeans` |
| `materials` | lowercase slug | `lithium`, `copper` |
| `products` | lowercase slug | `semiconductors`, `ev_batteries` |
| `companies` | lowercase slug | `tsmc`, `aramco` |
| `sources` | lowercase slug | `faostat`, `open-meteo` |

### Schemas

`profiles/SCHEMAS/{kind}.schema.json` — descriptive schema per kind.

### Indexes

`profiles/INDEX_{kind}.json` — top-level, auto-generated.
Each entry: `{id, kind, name, region, tags?, sector?}`.

- Updated incrementally on `put_profile()`
- Full rebuild via `rebuild_index(kind?)`
- `find_profile(query, region?)` merges all for cross-kind search

### Profile tools

| Tool | Purpose |
|------|---------|
| `get_profile(kind, id, region?)` | Read a profile (scans all regions if omitted) |
| `put_profile(kind, id, data, region?)` | Create/merge (default: global) |
| `list_profiles(kind, region?)` | List profiles, optionally by region |
| `find_profile(query, region?)` | Cross-kind search by name/ID/tag |
| `search_profiles(kind, field, value, region?)` | Field-level search |
| `list_regions()` | List regions and their kinds |
| `rebuild_index(kind?)` | Rebuild indexes from disk |
| `lint_profiles(kind?, id?)` | Validate against schema |

### Snapshot tools (same API + time fields)

| Tool | Purpose |
|------|---------|
| `snapshot(kind, entity, type, data, region?, ...)` | Store timestamped data in snap_{kind} |
| `history(kind, entity, type?, region?, after?, before?)` | Query snapshot history |
| `trend(kind, entity, type, field, periods?)` | Extract field trend |
| `nearby(kind, lon, lat, max_km?, type?)` | Geo proximity search |
| `event(subtype, summary, data, region?, ...)` | Log signal event |
| `recent_events(subtype?, severity?, region?, ...)` | Query recent events |
| `archive_snapshot(kind, entity, type, data, region?)` | Long-term storage in arch_{kind} |
| `archive_history(kind, entity, type?, region?, ...)` | Query archive |
| `compact(kind, entity, type, older_than_days?)` | Downsample to archive |
| `aggregate(kind, pipeline, archive?)` | Raw aggregation pipeline |
| `chart(kind, entity, type, fields, ...)` | Generate Plotly chart |

## Environment Variables

### Signals Stack (`.env`)
- `MONGO_URI` — MongoDB Atlas connection string (database: `signals`)
- `PROFILES_DIR` — path to profiles directory (default: `./profiles`)
- Optional API keys: `FRED_API_KEY`, `ACLED_API_KEY`, `EIA_API_KEY`, `COMTRADE_API_KEY`, `GOOGLE_API_KEY`, `AISSTREAM_API_KEY`, `CF_API_TOKEN`, `USDA_NASS_API_KEY`
- Full reference: `docs/api-keys.md`

### LibreChat (`~/LibreChat/.env`)
- `MONGO_URI` — MongoDB Atlas connection string (database: `LibreChat`)
- `CREDS_KEY`, `CREDS_IV`, `JWT_SECRET`, `JWT_REFRESH_SECRET` — auto-generated by setup.sh
- LLM keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENROUTER_API_KEY`
- `SEARCH=false` (Meilisearch disabled)

## Current Status (see TODO.md)

**Completed**: Repo init, cleanup, LibreChat full integration, CI release workflow, `ta` ops tool, data repo automation, code review fixes (security + correctness), chart tool + HTTP endpoint, profile INDEX.json, API keys doc, setup doc, test suite (87 tests: 45 bats + 42 pytest) + CI

**Next priorities (P0)**:
- Validate combined trading-data server runs without errors
- Test signals store against live Atlas M0
- Populate profiles at scale (~200 countries, ~500 stocks, ~100 ETFs, ~75 sources)

**Not yet done**: End-to-end Uberspace deployment test (P4), periodic ingest scheduler (P1), alert/threshold system (P1)

## Testing

### Frameworks
- **Shell scripts**: [bats-core](https://github.com/bats-core/bats-core) (Bash Automated Testing System) — 45 tests across 8 `.bats` files
- **Python**: [pytest](https://docs.pytest.org/) — 42 tests in `test_store.py` for profile CRUD, index, lint, search logic
- **Total**: 87 tests

### Running Tests
```bash
# Run all shell tests
bats tests/*.bats

# Run all Python tests
python -m pytest tests/test_store.py -v

# Run everything
bats tests/*.bats && python -m pytest tests/test_store.py -v

# Run a specific bats file
bats tests/test_ta_cron.bats

# Syntax check only (fast)
bash -n librechat-uberspace/scripts/TradeAssistant.sh
```

### Test Architecture

**Shell tests (bats)**:
- Each test gets a **sandboxed `$HOME`** via `mktemp -d` — no side effects on the real system
- External commands (`supervisorctl`, `uberspace`, `hostname`, `crontab`) are **stubbed** with scripts prepended to `$PATH`
- Git operations use **local bare repos** as fake remotes (no network needed)
- SSH keys are pre-created to skip interactive prompts in `setup-data-repo.sh`
- `$REAL_GIT` is saved before stubbing so git stubs can delegate non-intercepted calls

**Python tests (pytest)**:
- `conftest.py` mocks `pymongo` and `fastmcp` at import time — no MongoDB or MCP runtime needed
- Tests exercise pure-Python profile, index, lint, and search logic from `src/store/server.py`
- Each test gets a **temporary profiles directory** via `tmp_path` fixture with `monkeypatch`

### Test Coverage

| File | Tests | Framework | Covers |
|------|-------|-----------|--------|
| `test_store.py` | 42 | pytest | Profile CRUD, region discovery, path safety, index build/update, find/search, lint, schema validation |
| `test_ta_dispatch.bats` | 10 | bats | `ta help`, `status`, `version`, `restart`, `rollback`, aliases |
| `test_setup.bats` | 9 | bats | Install/update modes, `.env` generation, `librechat.yaml` templating, Node.js version check |
| `test_ta_cron.bats` | 6 | bats | Data sync commits, profile auto-commit, schedule gating |
| `test_setup_data_repo.bats` | 6 | bats | Directory structure, `.gitignore`, cron setup, idempotency |
| `test_deploy_conf.bats` | 5 | bats | Config loading, env overrides, variable defaults |
| `test_ta_sync.bats` | 3 | bats | Sync with/without git repo, commit + push behavior |
| `test_nightly_commit.bats` | 3 | bats | Profile staging, no-op when clean, selective `git add` |
| `test_bootstrap.bats` | 2 | bats | Syntax validation for all `.sh` files |

### CI Integration (`.github/workflows/tests.yml`)
Runs on every push to `main` and on PRs:
- **shell-tests** job: installs bats from git, runs `bash -n` on all `.sh` files, then `bats tests/*.bats`
- **python-tests** job: sets up Python 3.11, installs pytest, runs `pytest tests/test_store.py`
- **shellcheck** job: runs ShellCheck at error severity on all scripts

### Writing New Tests

**Bats (shell)**:
1. Create `tests/test_<name>.bats`
2. Load helpers: `load helpers/setup`
3. Use `setup()` / `teardown()` with `setup_sandbox` / `teardown_sandbox`
4. Stub external commands with `stub_command "name" "body"` or write to `$STUBS_DIR/`
5. Use `init_mock_git_repo "$dir"` to create test git repos
6. Run `bats tests/test_<name>.bats` to verify

**Pytest (Python)**:
1. Add tests to `tests/test_store.py` (or create new `tests/test_<name>.py`)
2. Use the `profiles_dir` fixture for a temp profiles directory
3. Use the `store` fixture for access to `server.py` functions
4. Run `python -m pytest tests/test_<name>.py -v` to verify

## Conventions

- All shell scripts use `set -euo pipefail`
- All scripts load `deploy.conf` as first step
- Color output: green=success, yellow=warning, red=error, cyan=info
- Profile files: uppercase ISO codes for countries (DEU, USA), uppercase tickers for entities (AAPL, NVDA)
- Git tags: `vMAJOR.MINOR.PATCH` (triggers CI release)
- Cron sync logger tag: `ta-data-sync`
- `__HOME__` placeholder in `librechat.yaml` is replaced by `setup.sh` with actual `$HOME`
- After editing any `.sh` file, always run `bash -n <file>` to verify syntax — especially for `TradeAssistant.sh` which must work when piped via `curl | bash` (avoid complex nested quoting in that context)
