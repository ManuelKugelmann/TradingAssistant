# TODO — MCP Signals Stack

Global roadmap and task list. Updated 2026-03-06.

---

## P0 — Foundation (do first)

- [ ] **Validate all 12 domain servers run without errors**
      Smoke-test each `src/servers/*_server.py` with `fastmcp dev` or `python -c "import ..."`.
      Some may have import issues or broken API base URLs.
- [ ] **Test signals store against live Atlas M0**
      Verify `snapshot()`, `event()`, `history()`, `trend()` round-trip correctly.
      Ensure TTL indexes work (insert doc with short TTL, confirm deletion).
- [ ] **Populate seed country profiles** (~20 major economies)
      Currently only DEU and USA. Need at minimum: CHN, JPN, GBR, FRA, IND, BRA, KOR,
      AUS, CAN, RUS, SAU, ZAF, MEX, IDN, TUR, ITA, ESP, NLD, CHE, SGP.
- [ ] **Populate seed entity profiles** (~20 stocks, ~5 ETFs)
      Currently only AAPL, NVDA, VWO. Need major index constituents and key ETFs
      (SPY, QQQ, EEM, GLD, USO, etc.).
- [ ] **Add more source profiles** for the 75+ data sources
      Currently only 3 (usgs, faostat, open-meteo). Each FastMCP server maps to
      multiple sources — create profiles for at least the top 2 per domain.

---

## P0.5 — API Keys & Secret Storage

### Secret Storage Infrastructure
- [ ] **Set up GitHub Actions secrets for CI testing**
      Add all API keys as repository secrets so integration tests run in CI.
      Settings → Secrets and variables → Actions → New repository secret.
- [ ] **Document `.env` setup for local development**
      Expand `.env.example` with comments and signup URLs for each key.
      Ensure `tests/README.md` references `.env` loading for local test runs.
- [ ] **Evaluate secret management for Uberspace production**
      Currently keys live in `.env` files on disk. Consider: encrypted `.env` via
      `sops`/`age`, or a lightweight vault. At minimum ensure `.env` files are
      `chmod 600` and excluded from git.

### API Key Acquisition (all services)

**Free, unlimited — sign up and get key immediately:**

- [ ] **FRED_API_KEY** — Federal Reserve Economic Data
      Signup: https://fred.stlouisfed.org/docs/api/api_key.html
      Unlimited requests. Used by `macro_server` (`fred_series`, `fred_search`).
- [ ] **EIA_API_KEY** — US Energy Information Administration
      Signup: https://www.eia.gov/opendata/register.php
      Unlimited requests. Used by `commodities_server` (`energy_series`).
- [ ] **USDA_NASS_API_KEY** — USDA National Agricultural Statistics
      Signup: https://quickstats.nass.usda.gov/api/
      Unlimited requests. Used by `agri_server` (`usda_crop`).

**Free tier with limits — sign up and get key:**

- [ ] **GOOGLE_API_KEY** — Google Civic Information API
      Signup: https://console.cloud.google.com/apis/credentials
      Enable "Google Civic Information API". Generous free tier.
      Used by `elections_server` (`us_voter_info`).
- [ ] **COMTRADE_API_KEY** — UN Comtrade (international trade flows)
      Signup: https://comtradeplus.un.org/TradeFlow
      100 requests/day free. Used by `commodities_server` (`trade_flows`).
- [ ] **CF_API_TOKEN** — Cloudflare Radar (internet traffic analytics)
      Signup: https://dash.cloudflare.com/profile/api-tokens
      Create token with "Radar Read" permission. Free tier.
      Used by `infra_server` (`internet_traffic`).
- [ ] **AISSTREAM_API_KEY** — AIS Stream (vessel tracking)
      Signup: https://aisstream.io/
      Free tier available. Used by `transport_server` (`vessels_in_area`).
- [ ] **OPENSANCTIONS_API_KEY** — OpenSanctions (sanctions/PEP search)
      Signup: https://www.opensanctions.org/api/
      Free tier available. Used by `conflict_server` (`search_sanctions`).

**Research/academic access — requires application:**

- [ ] **ACLED_API_KEY + ACLED_EMAIL** — Armed Conflict Location & Event Data
      Signup: https://acleddata.com/register/
      Requires research justification. Used by `conflict_server` (`acled_events`).

---

## P1 — Integration & Data Pipeline

- [ ] **Build periodic ingest scheduler**
      Cron or lightweight scheduler that calls domain MCP servers → stores snapshots.
      E.g., weekly: fetch prices for all entity profiles; monthly: fetch macro indicators
      for all country profiles; continuous: poll disaster/event feeds.
- [ ] **Wire up profile ↔ snapshot cross-references**
      When a snapshot is stored for entity "AAPL", auto-link to the profile's risk factors,
      supply chain deps, and country exposures.
- [ ] **Add event-to-profile impact mapping**
      When an earthquake event hits country "JPN", auto-tag entities with `exposure.countries`
      containing "JPN".
- [ ] **Implement alert/threshold system**
      Source profiles have `signal.thresholds` — build logic that checks incoming events
      against thresholds and flags high-severity signals.

---

## P1.5 — Fix Failing Services & Fill Data Gaps

### Failing / Degraded Services

- [ ] **UCDP API now requires auth token (Feb 2026)**
      Contact UCDP API maintainer to request free access token.
      Token goes in `x-ucdp-access-token` HTTP header.
      Docs: https://ucdp.uu.se/apidocs/
      Alternative: download CSV datasets from https://ucdp.uu.se/downloads/ (CC BY 4.0).
      Update `conflict_server.py` to send token header + add `UCDP_API_TOKEN` env var.

- [ ] **OpenSanctions API now requires key (already fixed in code)**
      Signup at https://www.opensanctions.org/api/ — free tier available.
      `OPENSANCTIONS_API_KEY` env var already wired in `conflict_server.py`.

- [ ] **FAOSTAT intermittent 521 (Cloudflare origin errors)**
      `agri_server.py` FAO endpoints sometimes return 521/522.
      Consider adding retry logic or fallback to FAOSTAT bulk CSV downloads.
      Bulk data: https://www.fao.org/faostat/en/#data

- [ ] **OpenSky Network rate limiting / auth required for some endpoints**
      `transport_server.py` `flights_in_area` and `flight_history` may get 429s.
      Consider adding OpenSky credentials (free account) for higher rate limits.
      Signup: https://opensky-network.org/index.php/login

### New Data Sources — Shipping/Maritime Density & Flow

- [ ] **Add GMTDS (Global Maritime Traffic Density Service)**
      Free AIS-based shipping density from NGA/MapLarge.
      API: `https://gmtds.maplarge.com/ogc/meta/gmd/ais:density`
      Formats: GridFloat, NetCDF, TIFF. 1km² resolution, 10yr history.
      Source: https://globalmaritimetraffic.org/
      → Add to `transport_server.py` as `maritime_density()` tool.

- [ ] **Add World Bank Global Shipping Traffic Density dataset**
      IMF partnership data: 6 density layers (commercial, fishing, oil&gas,
      passenger, leisure, global) at 500m resolution, 2015-2021.
      Source: https://datacatalog.worldbank.org/search/dataset/0037580
      → Could integrate as static reference data or periodic download.

- [ ] **Add NOAA Marine Cadastre AIS vessel traffic data (US waters)**
      Free AIS data for US waters with density map tooling.
      Source: https://hub.marinecadastre.gov/pages/vesseltraffic
      → Add to `transport_server.py` as `us_vessel_density()` tool.

- [ ] **Add HELCOM AIS density maps (Baltic Sea)**
      Free 1x1km annual density maps for Baltic, 2006-2024.
      GitHub: https://github.com/helcomsecretariat
      Source: https://metadata.helcom.fi/

### New Data Sources — Aviation Traffic Density & Flow

- [ ] **Add AirLabs flight tracking API**
      Real-time flights, schedules, airports, airlines, routes.
      Free tier: 1,000 queries/month. Dev tier: $49/month, 25k queries.
      Signup: https://airlabs.co/
      → Add to `transport_server.py` as `flight_density()` or enhance existing
      OpenSky tools with AirLabs as higher-quality alternative.

- [ ] **Add Aviationstack flight status API**
      Real-time & historical flight data, airline routes, airports.
      Free tier: 100 requests/month.
      Signup: https://aviationstack.com/
      → Could serve as fallback when OpenSky is rate-limited.

- [ ] **Integrate OpenFlights route data for density mapping**
      Free open dataset of airline routes, airports, airlines.
      Source: https://openflights.org/data
      → Static dataset for building flight network/density visualizations.

### New Data Sources — Road/Ground Traffic Density

- [ ] **Add TomTom Traffic API (free tier)**
      Traffic density, flow, and incident data worldwide.
      Free developer tier available.
      Signup: https://developer.tomtom.com/
      → New `traffic_server.py` or add to `transport_server.py`.

- [ ] **Add HERE Traffic API (free tier)**
      Real-time traffic flow + incidents, map tiles.
      Freemium developer plan.
      Signup: https://developer.here.com/
      → Alternative or complement to TomTom.

- [ ] **Curate open traffic data from GraphHopper collection**
      Community-maintained list of open traffic data sources by country.
      Source: https://github.com/graphhopper/open-traffic-collection
      → Reference for country-specific free traffic data.

### New Data Sources — Military Movements & OSINT

- [ ] **Add GDELT (Global Database of Events, Language, and Tone)**
      Largest open event database: 300+ event categories, updated every 15 min.
      Free, no auth required. BigQuery + CSV + API access.
      Source: https://www.gdeltproject.org/
      Stability Dashboard API: https://blog.gdeltproject.org/
      → New `osint_server.py` or add to `conflict_server.py`.
      Covers: protests, military actions, diplomatic events, conflict, peace.

- [ ] **Add ViEWS conflict forecasting data**
      AI-based armed conflict predictions, 1-36 months ahead, monthly updates.
      Open-source, free access.
      Source: https://viewsforecasting.org/
      → Add to `conflict_server.py` as `conflict_forecast()` tool.

- [ ] **Track military aircraft via ADS-B (OpenSky/ADS-B Exchange)**
      OpenSky already integrated. Military aircraft with transponders on are visible.
      ADS-B Exchange: community-driven, unfiltered (unlike FlightRadar24).
      → Enhance `transport_server.py` with military aircraft type filter.

### New Data Sources — Satellite Imagery & Earth Observation

- [ ] **Add NASA GIBS API (Global Imagery Browse Services)**
      1,000+ satellite imagery products, most updated daily, 30yr archive.
      Free, open, no auth. Supports WMTS/WMS.
      Source: https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api
      → New `satellite_server.py` for near-real-time Earth observation.

- [ ] **Add Spectator Earth API (satellite overpass tracking)**
      Real-time tracking of Sentinel-2, Landsat-8/9, Sentinel-1 overpasses.
      Free tier for non-commercial use.
      Source: https://api.spectator.earth/
      → Add to `satellite_server.py` for acquisition plan awareness.

- [ ] **Add Copernicus Data Space Ecosystem access**
      Free access to all Sentinel satellite data + processing tools.
      Source: https://dataspace.copernicus.eu/
      → Reference for on-demand satellite imagery retrieval.

### New Data Sources — Supply Chain & Port Congestion

- [ ] **Evaluate Portcast port congestion API**
      Real-time congestion data for 1,000+ ports: vessel wait times, dwell times.
      Commercial API, but publishes free weekly congestion snapshots.
      Source: https://www.portcast.io/
      → Could scrape weekly snapshot or integrate paid API if justified.

- [ ] **Evaluate Vizion TradeView for container tracking**
      Container tracking events, port efficiency, carrier performance.
      Commercial: https://www.vizionapi.com/
      → Evaluate ROI for trade signal generation.

---

## P2 — Server Improvements

- [ ] **Add cross-reference validation to profile linter**
      `lint_profiles()` currently does basic checks (required fields, types).
      Add a `deep=True` mode that validates cross-references: country ISO3 codes
      in `exposure.countries` exist as profiles, `trade.top_partners` resolve,
      source `mcp` fields match actual server names, supply chain entity IDs exist.

- [ ] **Add error handling and retries to domain servers**
      Most servers do bare `httpx.get()` calls with no retry, timeout, or error wrapping.
      Add consistent error responses and configurable timeouts.
- [ ] **Add async support to signals store**
      `server.py` uses sync `pymongo`. Consider `motor` for async MongoDB if needed
      for concurrent snapshot ingestion.
- [ ] **Add rate limiting awareness to source servers**
      Some APIs (ACLED, Google Civic, AIS Stream) have rate limits. Track and respect them.
- [ ] **Add health check tool to each server**
      `health()` tool that returns status, last successful call time, and API availability.

---

## P3 — Profile Expansion

- [ ] **Generate 200 country profiles from World Bank / CIA Factbook data**
      Script to fetch and populate `profiles/countries/` from free APIs.
- [ ] **Generate entity profiles from SEC EDGAR / Yahoo Finance**
      Script to fetch top stocks by market cap and populate `profiles/entities/stocks/`.
- [ ] **Add crypto profiles** (BTC, ETH, SOL, and top-20 by market cap)
      `profiles/entities/crypto/` — currently empty.
- [ ] **Add index profiles** (SPX, NDX, DJI, FTSE, DAX, N225, etc.)
      `profiles/entities/indices/` — currently empty.
- [ ] **Add ETF profiles** for key sector/country/commodity exposure
      VWO is the only one. Need SPY, QQQ, EEM, GLD, XLE, XLF, etc.

---

## P4 — Deployment & Ops

- [ ] **Test Uberspace deployment end-to-end**
      Run `scripts/bootstrap-uberspace.sh` on a live Uberspace host.
      Verify supervisord services start, logs rotate, .env is picked up.
- [ ] **Test LibreChat deployment end-to-end**
      Run the `librechat-uberspace/` deployment package. Verify LibreChat connects
      to Atlas, MCP servers respond, git-versioned data sync works.
- [ ] **Set up CI/CD** (GitHub Actions)
      Lint Python (`ruff`), run basic import checks, validate JSON profiles against schemas.
      Release workflow exists (`.github/workflows/release.yml`) — still need lint/test workflow.
- [ ] **Add monitoring / health dashboard**
      Simple status page or script that checks: Atlas connection, each MCP server,
      last successful ingest timestamp per source.

---

## P5 — Documentation & Polish

- [ ] **Add CONTRIBUTING.md** with profile contribution guidelines
      How to add a new country/entity/source profile, naming conventions, schema rules.
- [ ] **Iterate on profile schemas based on actual MCP data**
      Run each domain server, inspect the data it returns, and update `_schema.json`
      files so profile fields match the real structure of MCP responses.
      Add fields that capture what the APIs actually provide; remove speculative ones.
- [ ] **Add JSON Schema validation** (proper `$schema` with `jsonschema` library)
      Current `_schema.json` files are descriptive, not machine-validatable.
      Convert to proper JSON Schema draft-07 or later.
- [ ] **Document MCP client integration** (how to connect from Claude/LibreChat)
      Add a `docs/mcp-client-setup.md` showing how to configure MCP clients
      to talk to the signals store and domain servers.
- [ ] **Consolidate overlapping docs**
      `trading-mcp-inventory.md` and `trading-stack-full.md` overlap significantly.
      Consider merging or clearly delineating scope.

---

## Completed

- [x] **Repo init** — initial structure, 12 domain servers, signals store, profiles
- [x] **Repo cleanup** — add .gitignore, .env.example, fix nested dirs, align filenames,
      fix scripts, create TODO.md (2026-03-03)
- [x] **LibreChat full integration** — wire 12 trading MCPs + signals store into
      librechat.yaml, add __HOME__ path placeholders, add .env.example for LC,
      add GitHub Actions release workflow, update setup.sh for Python MCP deps,
      rewrite README with QuickStart (2026-03-03)
- [x] **MCP server test suite** — 134 tests (unit + integration) for all 12 domain
      servers + signals store. Unit tests with respx mocks, integration tests hitting
      real free APIs with graceful skip on failures. Fixed FastMCP v3 compat
      (`description=` → `instructions=`), OpenSanctions auth, transport null-states
      bug, store internal cross-call issue. (2026-03-06)
