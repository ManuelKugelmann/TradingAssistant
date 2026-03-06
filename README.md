### TradingAssistant

- Chat-based access to 75+ free data sources across 12 domains
- Covers macro, weather, disasters, commodities, health, conflict, and more
- Hybrid storage: structured profiles + time-series snapshots

## Data Sources and Storage

| | Layer | What | Format | Update | Size |
|---|-------|------|--------|--------|------|
| 📁 | **Profiles** | Identity, exposure, risk | JSON on disk, git-tracked | Manual / monthly | ~5 MB |
| ☁️ | **Snapshots** | Indicators, prices, events | MongoDB Atlas M0, TTL | Hourly → quarterly | ~60 MB/yr |
| 🔌 | **Live queries** | Current data from 75+ APIs | On-demand, no storage | Real-time | — |

Profile = what it **is**. Snapshot = what was measured **when**. MCP = current **live** state.

## Data Coverage (75+ sources, 12 domains)

| Domain | Sources | Auth | Key APIs |
|--------|---------|------|----------|
| Agriculture | 6 | Mixed | FAOSTAT, USDA NASS/FAS |
| Disasters | 6 | Mostly none | USGS, GDACS, NASA FIRMS/EONET |
| Elections | 6 | Mixed | IFES, V-Dem, Google Civic |
| Macro | 8 | Mostly none | FRED, World Bank, IMF, ECB |
| Weather | 5 | Mostly none | Open-Meteo, NOAA SWPC |
| Commodities | 5 | Mixed | UN Comtrade, EIA |
| Military | 7 | Mixed | UCDP, ACLED, OpenSanctions |
| Medical | 9 | Mostly none | WHO, disease.sh, OpenFDA |
| Shipping | 3 | Mixed | AIS Stream, OpenSky |
| Water | 4 | None | USGS Water, Drought Monitor |
| Humanitarian | 4 | None | UNHCR, OCHA HDX |
| Internet | 4 | Mixed | Cloudflare Radar, RIPE Atlas |

28 sources need zero API key. 15 need a free key. 0 paid.

## Deploy to Uberspace

```bash
ssh assist@assist.uber.space
curl -sL https://raw.githubusercontent.com/ManuelKugelmann/TradingAssistant/main/librechat-uberspace/scripts/TradeAssistant.sh | bash
```

Then configure `nano ~/mcps/.env` and `nano ~/LibreChat/.env`, then `supervisorctl start librechat`. Re-run safe — skips what's already done, preserves config.

## MongoDB Atlas Setup (free M0 cluster)

1. **Create account** — go to [cloud.mongodb.com](https://cloud.mongodb.com/) and sign up (free)
2. **Create a cluster** — choose **M0 Free Tier**, pick any cloud provider/region
3. **Create a database user** — Security → Database Access → Add New Database User → password auth
4. **Allow network access** — Security → Network Access → Add IP Address
   - For Uberspace: add `185.26.156.0/22` (Uberspace IP range) or your server's IP
   - For local dev: add your current IP or `0.0.0.0/0` (allow all, less secure)
5. **Get the connection string** — Deployment → Database → Connect → Drivers → copy the URI
   - Format: `mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority`
6. **Configure the project** — paste the URI into your `.env` files:

```bash
# Signals store (~/.env or ~/mcps/.env)
MONGO_URI=mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/signals?retryWrites=true&w=majority

# LibreChat (~/LibreChat/.env) — uses a separate database name
MONGO_URI=mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/LibreChat?retryWrites=true&w=majority
```

The signals store uses the `signals` database for snapshots (TTL auto-pruned). LibreChat uses `LibreChat` for chat history and user accounts. Both can share the same M0 cluster.

## Quick Start (local dev)

```bash
git clone https://github.com/ManuelKugelmann/TradingAssistant.git
cd TradingAssistant
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with MONGO_URI + API keys
python src/store/server.py
```

## License

MIT
