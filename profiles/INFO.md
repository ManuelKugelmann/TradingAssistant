# Profiles Directory

Profiles describe anything tradeable or trade-relevant. Organized by
**geographic region** then **kind**, with per-kind indexes and schemas
at the top level.

## Structure

```
profiles/
├── INFO.md                        ← this file
├── INDEX_{kind}.json              ← per-kind indexes (auto-generated)
│
├── SCHEMAS/                       ← descriptive schemas (one per kind)
│   ├── countries.schema.json
│   ├── stocks.schema.json
│   ├── etfs.schema.json
│   ├── crypto.schema.json
│   ├── indices.schema.json
│   ├── commodities.schema.json
│   ├── crops.schema.json
│   ├── materials.schema.json
│   ├── products.schema.json
│   ├── companies.schema.json
│   └── sources.schema.json
│
├── north_america/                 ← economic region folders
│   ├── countries/USA.json
│   ├── stocks/AAPL.json
│   └── companies/...
├── latin_america/
├── europe/
│   ├── countries/DEU.json
│   └── stocks/SAP.json
├── mena/                          ← Middle East & North Africa
├── sub_saharan_africa/
├── south_asia/
├── east_asia/
├── southeast_asia/
├── central_asia/
├── oceania/
├── arctic/                        ← interest regions
├── antarctic/
└── global/                        ← non-geographic (ETFs, indices, commodities, ...)
    ├── etfs/VWO.json
    ├── indices/
    ├── commodities/
    ├── crops/
    ├── materials/
    └── sources/faostat.json
```

## Regions

| Region | Description |
|--------|-------------|
| `north_america` | USA, Canada, Mexico |
| `latin_america` | Central America, Caribbean, South America |
| `europe` | EU + non-EU European countries |
| `mena` | Middle East & North Africa |
| `sub_saharan_africa` | Sub-Saharan Africa |
| `south_asia` | India, Pakistan, Bangladesh, etc. |
| `east_asia` | China, Japan, Korea, Taiwan, Mongolia |
| `southeast_asia` | ASEAN countries |
| `central_asia` | Kazakhstan, Uzbekistan, etc. |
| `oceania` | Australia, New Zealand, Pacific Islands |
| `arctic` | Arctic region (climate, resources, shipping) |
| `antarctic` | Antarctic region (climate, research) |
| `global` | Non-geographic: ETFs, indices, commodities, crops, materials, sources |

## Kinds

| Kind | ID Convention | Example IDs | Schema |
|------|---------------|-------------|--------|
| countries | ISO3 uppercase | DEU, USA, CHN | [countries.schema.json](SCHEMAS/countries.schema.json) |
| stocks | Ticker uppercase | AAPL, NVDA, SAP | [stocks.schema.json](SCHEMAS/stocks.schema.json) |
| etfs | Ticker uppercase | VWO, SPY, QQQ | [etfs.schema.json](SCHEMAS/etfs.schema.json) |
| crypto | Symbol uppercase | BTC, ETH, SOL | [crypto.schema.json](SCHEMAS/crypto.schema.json) |
| indices | Symbol uppercase | SPX, NDX, DJI | [indices.schema.json](SCHEMAS/indices.schema.json) |
| commodities | lowercase slug | crude_oil, gold | [commodities.schema.json](SCHEMAS/commodities.schema.json) |
| crops | lowercase slug | corn, wheat | [crops.schema.json](SCHEMAS/crops.schema.json) |
| materials | lowercase slug | lithium, copper | [materials.schema.json](SCHEMAS/materials.schema.json) |
| products | lowercase slug | semiconductors | [products.schema.json](SCHEMAS/products.schema.json) |
| companies | lowercase slug | tsmc, aramco | [companies.schema.json](SCHEMAS/companies.schema.json) |
| sources | lowercase slug | faostat, usgs | [sources.schema.json](SCHEMAS/sources.schema.json) |

## Index Files

Top-level `INDEX_{kind}.json` per kind — array of `{id, kind, name, region, tags?, sector?}`.

- Auto-updated on `put_profile()` calls
- Full rebuild via `rebuild_index(kind?)`
- `find_profile(query, region?)` merges all indexes for cross-kind search
- Region key always present for geographic filtering

## MongoDB Collections

Per-kind timeseries collections mirror the profile structure:

| Collection | TTL | Use |
|------------|-----|-----|
| `snap_{kind}` | 365 days | Recent snapshots (hours granularity) |
| `arch_{kind}` | none | Long-term archive (days granularity) |
| `events` | 365 days | Cross-kind signal events |

All docs include `meta.region` matching the profile's geographic region.
Optional `location` GeoJSON Point field for spatial queries via `nearby()`.

## Tools

### Profile tools (file-based)

| Tool | Purpose |
|------|---------|
| `get_profile(kind, id, region?)` | Read a profile (scans all regions if omitted) |
| `put_profile(kind, id, data, region?)` | Create/merge profile (default: global) |
| `list_profiles(kind, region?)` | List profiles, optionally by region |
| `find_profile(query, region?)` | Cross-kind search by name/ID/tag |
| `search_profiles(kind, field, value, region?)` | Field-level search |
| `list_regions()` | List regions and their kinds |
| `rebuild_index(kind?)` | Rebuild indexes from disk |
| `lint_profiles(kind?, id?)` | Validate against schema |

### Snapshot tools (MongoDB, same API + time fields)

| Tool | Purpose |
|------|---------|
| `snapshot(kind, entity, type, data, region?, ...)` | Store timestamped data |
| `history(kind, entity, type?, region?, after?, before?)` | Query history |
| `trend(kind, entity, type, field, periods?)` | Extract field trend |
| `nearby(kind, lon, lat, max_km?, type?)` | Geo proximity search |
| `event(subtype, summary, data, region?, ...)` | Log signal event |
| `recent_events(subtype?, severity?, region?, ...)` | Query recent events |
| `archive_snapshot(kind, entity, type, data, region?)` | Long-term storage |
| `archive_history(kind, entity, type?, region?, ...)` | Query archive |
| `compact(kind, entity, type, older_than_days?)` | Downsample to archive |
| `aggregate(kind, pipeline, archive?)` | Raw aggregation pipeline |
| `chart(kind, entity, type, fields, ...)` | Generate Plotly chart |
