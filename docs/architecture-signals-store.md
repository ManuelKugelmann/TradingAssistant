# MCP Signals Store — Hybrid Architecture

> JSON file profiles (stable, git-tracked) + MongoDB Atlas M0 snapshots (volatile, TTL)

## Storage Split

```
 Stable / slow-changing?              Volatile / time-series?
 Human-editable? Identity?            Auto-collected? Measurements?
          │                                    │
          ▼                                    ▼
     📁 JSON files                       ☁️ Atlas M0
     (git-tracked)                    (signals.snapshots)
```

| Criteria | 📁 JSON Profile | ☁️ Atlas Snapshot |
|----------|----------------|-------------------|
| What | Identity, structure, exposure, curated risk factors | Periodic readings, events, price history |
| Update freq | Manual / monthly | Hourly → quarterly |
| Format | 1 file per entity, structured dirs | Documents with TTL |
| Versioning | `git log` | TTL auto-prune |
| Size | ~5 MB total (200 countries + 2000 entities) | ~5 MB/year growth |

---

## 📁 File Profiles — Directory Layout

```
profiles/
├── .git/
├── countries/
│   ├── _schema.json
│   ├── DEU.json
│   ├── USA.json
│   └── CHN.json              (~200 files)
├── entities/
│   ├── _schema.json
│   ├── stocks/
│   │   ├── AAPL.json
│   │   ├── NVDA.json
│   │   └── ...
│   ├── etfs/
│   │   ├── VWO.json
│   │   └── SPY.json
│   ├── indices/
│   │   └── SPX.json
│   └── crypto/
│       └── BTC.json          (~2000 files)
└── sources/
    ├── usgs.json
    ├── faostat.json
    └── ...                   (MCP source metadata)
```

### Country Profile (`countries/DEU.json`)

```json
{
  "id": "DEU",
  "name": "Germany",
  "iso2": "DE",
  "region": "Europe",
  "subregion": "Western Europe",
  "currency": "EUR",
  "capital": "Berlin",
  "population_est": 84300000,
  "trade": {
    "top_exports": ["vehicles", "machinery", "chemicals"],
    "top_partners": ["USA", "CHN", "FRA", "NLD", "POL"],
    "major_ports": ["Hamburg", "Bremerhaven"],
    "chokepoint_exposure": ["Suez"]
  },
  "exposure": {
    "commodities_import": ["natural_gas", "oil", "rare_earths"],
    "energy_mix": {"renewables": 0.52, "gas": 0.22, "coal": 0.18, "nuclear": 0.0},
    "risk_factors": ["russian_gas_dependency", "china_trade_exposure", "aging_demographics"]
  },
  "ratings": {
    "credit": "AAA",
    "democracy_index": 8.67,
    "press_freedom_rank": 21,
    "corruption_perception": 79
  },
  "_updated": "2026-02-15",
  "_sources": ["worldbank", "cia_factbook", "transparency_intl"]
}
```

### Entity Profile (`entities/stocks/NVDA.json`)

```json
{
  "id": "NVDA",
  "name": "NVIDIA Corporation",
  "type": "stock",
  "exchange": "NASDAQ",
  "sector": "Technology",
  "industry": "Semiconductors",
  "country": "USA",
  "founded": 1993,
  "employees": 29600,
  "exposure": {
    "countries": ["USA", "TWN", "CHN", "KOR"],
    "commodities": ["silicon", "rare_earths", "cobalt"],
    "supply_chain": ["TSMC", "Samsung", "SK Hynix"],
    "risk_factors": ["china_export_controls", "tsmc_concentration", "ai_regulation"]
  },
  "tags": ["ai", "datacenter", "gaming", "automotive", "fab_light"],
  "_updated": "2026-02-20",
  "_sources": ["sec_edgar", "manual"]
}
```

### Source Metadata (`sources/usgs.json`)

```json
{
  "id": "usgs",
  "name": "USGS Earthquake Hazards",
  "mcp": "disasters-server",
  "tool": "get_earthquakes",
  "refresh": "continuous",
  "snapshot_type": "event",
  "default_params": {"min_magnitude": 4.5},
  "signal_threshold": {"severity_high": {"min_magnitude": 6.0}},
  "ttl_days": 180
}
```

---

## ☁️ Atlas M0 — Snapshots Collection

Single collection `signals.snapshots`, discriminated by `type` field.

### Indexes

```javascript
{ entity: 1, type: 1, ts: -1 }   // main query path
{ type: 1, ts: -1 }              // "all price snapshots this week"
{ expires_at: 1 }                 // TTL auto-delete
{ "data.$**": 1 }                // wildcard for ad-hoc queries
```

### Indicator Snapshot

```javascript
{
  entity: "DEU",
  type: "indicators",
  ts: ISODate("2026-02-28"),
  data: {
    gdp_growth_pct: 0.3,
    inflation_pct: 2.1,
    unemployment_pct: 5.8,
    mil_spend_pct_gdp: 1.5
  },
  source: "worldbank",
  expires_at: ISODate("2027-02-28")
}
```

### Price Snapshot

```javascript
{
  entity: "AAPL",
  type: "price",
  ts: ISODate("2026-02-28"),
  data: { open: 230.1, close: 232.5, high: 234.0, low: 229.8, volume: 52e6 },
  source: "yahoo_finance",
  expires_at: ISODate("2027-02-28")
}
```

### Event

```javascript
{
  entity: null,
  type: "event",
  subtype: "earthquake",
  severity: "high",
  countries: ["TON"],
  entities: ["MUV2.DE"],
  summary: "M6.2 Tonga, tsunami warning",
  data: { mag: 6.2, depth_km: 33, tsunami: true },
  impact: { sectors: ["shipping", "insurance"], signal: "risk-off" },
  source: "usgs",
  ts: ISODate("2026-02-28T15:30:00Z"),
  expires_at: ISODate("2026-08-28")
}
```

---

## What Lives Where

| Data | 📁 Profile | ☁️ Atlas |
|------|-----------|---------|
| Country name, region, currency | ✅ | |
| Country GDP quarterly reading | | ✅ `indicators` |
| Company sector, exchange, employees | ✅ | |
| Weekly/daily price | | ✅ `price` |
| ETF holdings, top countries | ✅ | |
| Quarterly earnings | | ✅ `fundamentals` |
| Supply chain / risk factors | ✅ | |
| Earthquake / outbreak events | | ✅ `event` |
| Trade partners, export structure | ✅ | |
| Sanctions list changes | | ✅ `event` |
| MCP source config & thresholds | ✅ | |

**Rule:** Profile = what it **is**. Snapshot = what happened / was measured **when**.

---

## One MCP Server, 20 Tools

The signals store is a **single FastMCP server** (`src/store/server.py`) that exposes 20 tools. LibreChat sees it as one MCP server entry in `librechat.yaml` — all profile management, snapshot storage, querying, charting, and archival are tools within that one server.

### Profile Tools (8 tools, file-backed)

| Tool | Description |
|------|-------------|
| `get_profile(kind, id, region?)` | Read a profile (scans all regions if omitted) |
| `put_profile(kind, id, data, region?)` | Create/merge profile fields |
| `list_profiles(kind, region?)` | List profiles, optionally by region |
| `find_profile(query, region?)` | Cross-kind search by name/ID/tag |
| `search_profiles(kind, field, value, region?)` | Field-level search by dot-path |
| `list_regions()` | List regions and their kinds |
| `rebuild_index(kind?)` | Rebuild INDEX files from disk |
| `lint_profiles(kind?, id?)` | Validate profiles against schema |

### Snapshot Tools (9 tools, Atlas-backed)

| Tool | Description |
|------|-------------|
| `snapshot(kind, entity, type, data, ...)` | Store timestamped reading |
| `event(subtype, summary, data, ...)` | Log signal event with severity + cross-refs |
| `history(kind, entity, type?, after?, before?)` | Query snapshot series |
| `recent_events(subtype?, severity?, region?, ...)` | Query recent events |
| `trend(kind, entity, type, field, periods?)` | Extract single field trend over time |
| `nearby(kind, lon, lat, max_km?, type?)` | Geo proximity search (2dsphere) |
| `aggregate(kind, pipeline, archive?)` | Raw MongoDB aggregation pipeline |
| `chart(kind, entity, type, fields, ...)` | Generate Plotly chart |

### Archive Tools (3 tools, Atlas-backed)

| Tool | Description |
|------|-------------|
| `archive_snapshot(kind, entity, type, data, ...)` | Long-term storage in arch_{kind} |
| `archive_history(kind, entity, type?, ...)` | Query archive |
| `compact(kind, entity, type, older_than_days?)` | Downsample snapshots to archive |

---

## Refresh Schedule

```
┌─────────────────────────┬──────────────┬──────────────────────────┐
│ What                    │ Frequency    │ Source MCPs              │
├─────────────────────────┼──────────────┼──────────────────────────┤
│ Country indicators      │ Monthly      │ World Bank, FRED, WHO    │
│ Country profiles        │ Quarterly    │ Manual / LLM review      │
│ Entity prices           │ Weekly       │ Yahoo Finance            │
│ Entity fundamentals     │ Quarterly    │ SEC/EDGAR                │
│ Entity profiles         │ On change    │ Manual / LLM review      │
│ Events                  │ Continuous   │ USGS, GDACS, FIRMS,      │
│                         │              │ disease.sh, ReliefWeb    │
│ Event pruning           │ Nightly      │ TTL auto-delete          │
│ Profile git commit      │ Nightly      │ Cron                     │
└─────────────────────────┴──────────────┴──────────────────────────┘
```

---

## Storage Budget

| Store | Records | Size | Growth |
|-------|---------|------|--------|
| 📁 Country profiles | ~200 files | ~600 KB | Negligible |
| 📁 Entity profiles | ~2000 files | ~4 MB | ~100 files/year |
| ☁️ Indicator snapshots | ~200/month | ~2.4 MB/year | Stable |
| ☁️ Price snapshots | ~2000/week | ~50 MB/year | Grows with entities |
| ☁️ Events | ~50-100/week | ~5 MB/year | Pruned by TTL |
| **Atlas M0 total** | | **~60 MB/year** | **512 MB = ~8 years** |

---

## Dependencies

- **Profiles:** Zero. Pure `json` + `pathlib` (stdlib).
- **Atlas:** `pymongo` + `MONGO_URI` env var.
- **MCP:** `fastmcp` + `httpx` (for data ingestion from source MCPs).

## Git Versioning for Profiles

```bash
# Nightly cron on Uberspace
cd ~/profiles && git add -A && \
  git diff --cached --quiet || \
  git commit -m "auto: $(date +%Y-%m-%d) profile updates"
```

`git log --oneline countries/DEU.json` → full change history.

---

## Integration with MCP Data Stack

```
 ┌──────────────────────┐
 │  75+ Source MCPs      │  ← Live query (no duplication)
 │  (weather, macro,     │
 │   disasters, health,  │
 │   shipping, conflict) │
 └──────────┬───────────┘
            │ periodic ingest
            ▼
 ┌──────────────────────┐     ┌─────────────────────┐
 │ ☁️ Atlas Snapshots    │ ──→ │ trend()             │
 │  indicators, prices,  │     │ recent_events()     │
 │  events               │     │ history()           │
 └──────────────────────┘     └─────────────────────┘
            │ references
            ▼
 ┌──────────────────────┐     ┌─────────────────────┐
 │ 📁 JSON Profiles      │ ──→ │ get_profile()       │
 │  countries, entities,  │     │ search_profiles()   │
 │  sources               │     │ put_profile()       │
 └──────────────────────┘     └─────────────────────┘
```

Profiles provide **context** (what is this entity, what are its risk factors).
Snapshots provide **time-series** (what happened, how did indicators change).
MCP sources provide **live state** (current price, latest earthquake, today's weather).
