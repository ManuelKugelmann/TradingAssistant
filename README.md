# MCP Signals Stack

> Hybrid intelligence platform: 75+ data sources, structured storage, Uberspace-deployable.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  📁 profiles/              (JSON files, git-tracked)        │
│  ├── countries/DEU.json    ← stable identity & exposure     │
│  ├── entities/stocks/      ← sector, supply chain, risk     │
│  └── sources/usgs.json     ← MCP source metadata            │
│                                                             │
│  ☁️ Atlas M0  signals.snapshots   (volatile, TTL)           │
│  ├── indicators  (GDP, CPI, unemployment — monthly)         │
│  ├── price       (OHLCV — weekly)                           │
│  ├── fundamentals (earnings — quarterly)                    │
│  └── event       (earthquakes, outbreaks, sanctions)        │
│                                                             │
│  🔌 75+ MCP data sources   (live query, no duplication)     │
│  ├── 12 FastMCP domain servers (~1,540 lines total)         │
│  └── 17 existing MCPs (npx/uvx/pip)                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Design principle:** Profile = what it **is**. Snapshot = what was measured **when**. MCP = current **live** state.

## Storage Split

| Store | What | Format | Update Freq |
|-------|------|--------|-------------|
| 📁 JSON profiles | Identity, exposure, risk factors | 1 file per entity, git-tracked | Manual / monthly |
| ☁️ Atlas M0 | Time-series snapshots, events | Documents with TTL auto-prune | Hourly → quarterly |
| 🔌 MCP sources | Live current data | API queries on demand | Real-time |

## Deploy to Uberspace (one-liner)

```bash
ssh assist@assist.uber.space
curl -sL https://raw.githubusercontent.com/ManuelKugelmann/TradingAssistant/main/install.sh | bash
```

Then configure: `nano ~/mcp-signals-stack/.env` and `nano ~/LibreChat/.env`, then `supervisorctl start librechat`.

Re-run safe — skips what's already done, preserves `.env` and config.

## Quick Start (local dev)

```bash
git clone https://github.com/ManuelKugelmann/TradingAssistant.git
cd TradingAssistant
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with MONGO_URI + API keys
python src/store/server.py
```

## Central Configuration

All deployment settings live in `deploy.conf` — edit once, applies everywhere:

```bash
UBER_USER=assist                  # Uberspace username
UBER_HOST=assist.uber.space       # Uberspace hostname
GH_USER=ManuelKugelmann           # GitHub username
GH_REPO_STACK=TradingAssistant    # This repo
```

Override via environment: `UBER_USER=other ./scripts/bootstrap-uberspace.sh`

## Project Structure

```
├── README.md
├── TODO.md                           ← Project roadmap & tasks
├── install.sh                        ← One-liner Uberspace install (idempotent)
├── deploy.conf                       ← Central config (all scripts source this)
├── .env.example                      ← Signals stack env vars
├── .gitignore
├── requirements.txt
│
├── docs/
│   ├── architecture-signals-store.md ← Hybrid storage design
│   ├── global-datasources-75.md      ← 75+ free API catalog
│   ├── uberspace-deployment.md       ← Uberspace stack guide
│   ├── trading-mcp-inventory.md      ← Existing MCP catalog
│   ├── trading-stack-full.md         ← Full stack inventory
│   └── librechat-uberspace-setup.md  ← LibreChat Lite deployment guide
│
├── src/
│   ├── store/
│   │   └── server.py                 ← Hybrid store (profiles + Atlas)
│   └── servers/
│       ├── agri_server.py            ← FAOSTAT, USDA
│       ├── commodities_server.py     ← UN Comtrade, EIA
│       ├── conflict_server.py        ← UCDP, ACLED, OpenSanctions
│       ├── disasters_server.py       ← USGS, GDACS, EONET
│       ├── elections_server.py       ← ReliefWeb, Google Civic
│       ├── health_server.py          ← WHO, disease.sh, OpenFDA
│       ├── humanitarian_server.py    ← UNHCR, HDX, ReliefWeb
│       ├── infra_server.py           ← Cloudflare Radar, RIPE
│       ├── macro_server.py           ← FRED, World Bank, IMF
│       ├── transport_server.py       ← OpenSky, AIS Stream
│       ├── water_server.py           ← USGS Water, Drought Monitor
│       └── weather_server.py         ← Open-Meteo, NOAA SWPC
│
├── profiles/                         ← Git-tracked JSON profiles
│   ├── countries/
│   │   ├── _schema.json
│   │   ├── DEU.json
│   │   └── USA.json
│   ├── entities/
│   │   ├── _schema.json
│   │   ├── stocks/   (AAPL.json, NVDA.json)
│   │   ├── etfs/     (VWO.json)
│   │   ├── crypto/
│   │   └── indices/
│   └── sources/
│       ├── usgs.json
│       ├── faostat.json
│       └── open-meteo.json
│
├── scripts/
│   ├── bootstrap-uberspace.sh        ← Uberspace setup
│   └── nightly-git-commit.sh         ← Auto-commit profiles
│
└── librechat-uberspace/              ← LibreChat Lite deployment package
    ├── README.md
    ├── config/
    │   ├── librechat.yaml
    │   └── .env.example              ← LibreChat env vars
    └── scripts/
        ├── bootstrap.sh
        ├── lc.sh
        ├── setup.sh
        └── setup-data-repo.sh
```

## Data Coverage (75+ sources, 12 domains)

| Domain | Sources | Auth | Key APIs |
|--------|---------|------|----------|
| 🌾 Agriculture | 6 | Mixed | FAOSTAT, USDA NASS/FAS |
| 🔥 Disasters | 6 | Mostly none | USGS, GDACS, NASA FIRMS/EONET |
| 🗳️ Elections | 6 | Mixed | IFES, V-Dem, Google Civic |
| 📊 Macro | 8 | Mostly none | FRED, World Bank, IMF, ECB |
| 🌧️ Weather | 5 | Mostly none | Open-Meteo, NOAA SWPC |
| ⛏️ Commodities | 5 | Mixed | UN Comtrade, EIA |
| ⚔️ Military | 7 | Mixed | UCDP, ACLED, OpenSanctions |
| 🏥 Medical | 9 | Mostly none | WHO, disease.sh, OpenFDA |
| 🚢 Shipping | 3 | Mixed | AIS Stream, OpenSky |
| 🌊 Water | 4 | None | USGS Water, Drought Monitor |
| 👥 Humanitarian | 4 | None | UNHCR, OCHA HDX |
| 🌐 Internet | 4 | Mixed | Cloudflare Radar, RIPE Atlas |

**28 sources need zero API key. 15 need a free key. 0 paid.**

## Storage Budget

| Store | Size | Growth |
|-------|------|--------|
| 📁 Profiles | ~5 MB | Negligible |
| ☁️ Atlas snapshots | ~60 MB/year | 512 MB = ~8 years free |

## Deployment

Default target: **assist.uber.space** (Uberspace.de, ~5 EUR/mo). No Docker, no root, no GPU.

| Method | Command | When |
|--------|---------|------|
| One-liner | `curl -sL .../install.sh \| bash` | First install or full re-setup |
| Release update | `lc u` | Production updates from tagged releases |
| Git pull | `lc pull` | Quick dev testing, no release needed |
| Re-install | `lc install` | Re-run installer (idempotent) |

See `librechat-uberspace/README.md` for detailed setup.

## License

MIT
