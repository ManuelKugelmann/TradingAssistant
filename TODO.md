# TODO — MCP Signals Stack

Global roadmap and task list. Updated 2026-03-03.

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
      Run `ta install` on a live Uberspace host.
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
