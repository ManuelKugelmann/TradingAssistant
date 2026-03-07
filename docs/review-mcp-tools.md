# MCP Tools Review — Consolidation & Provider-Agnostic Routing

**Date**: 2026-03-07
**Scope**: All 10 FastMCP sub-servers (store + 9 data domains) + 3 utility MCPs

---

## Executive Summary

The trading stack exposes **50+ tools** across 10 namespaces via a single combined FastMCP process, plus 3 utility MCPs (filesystem, memory, sqlite) via stdio. All servers are **self-hosted** — no cloud MCP services.

This review identifies:
1. **4 redundant tools** that wrap the same API endpoint or duplicate existing capability
2. **3 provider-agnostic routing opportunities** where multiple tools query different providers for the same concept
3. **2 utility MCP consolidation candidates** (optional, low priority)

---

## 1. Redundant Tools (Remove or Merge)

### 1.1 ReliefWeb Duplication — CRITICAL

| Tool | Server | Endpoint | Difference |
|------|--------|----------|------------|
| `conflict_reliefweb_reports` | conflict_server.py:95 | `POST api.reliefweb.int/v1/reports` | Generic query + country filter |
| `politics_election_reports` | elections_server.py:140 | `GET api.reliefweb.int/v1/reports` | Hardcoded `query="election"` |

**Same API, same data.** The elections variant just pre-fills `query="election"`. Users can already call `conflict_reliefweb_reports(query="election")` for identical results.

**Action**: Remove `politics_election_reports` from `elections_server.py`.

### 1.2 Military Spending Wrapper — LOW

| Tool | Server | Endpoint |
|------|--------|----------|
| `conflict_military_spending` | conflict_server.py:56 | `api.worldbank.org/.../MS.MIL.XPND.GD.ZS` |
| `econ_worldbank_indicator` | macro_server.py:41 | `api.worldbank.org/.../indicator/{indicator}` |

`military_spending(country, date)` is literally `worldbank_indicator(indicator="MS.MIL.XPND.GD.ZS", country, date)` with the indicator hardcoded. It's a convenience alias that adds tool surface area without adding capability.

**Action**: Remove `military_spending`. Document `MS.MIL.XPND.GD.ZS` as an example in `worldbank_indicator`'s docstring.

### 1.3 Earthquake Overlap — MEDIUM

| Tool | Server | Source | Scope |
|------|--------|--------|-------|
| `disaster_get_earthquakes` | disasters_server.py:10 | USGS | Earthquakes only, detailed (magnitude, alert, tsunami) |
| `disaster_get_disasters` | disasters_server.py:33 | GDACS | All disasters incl. earthquakes (lower detail) |
| `disaster_get_natural_events` | disasters_server.py:43 | NASA EONET | All events incl. earthquakes (lower detail) |

All three return earthquake data. GDACS and NASA EONET also cover earthquakes alongside floods, cyclones, volcanoes, etc.

**Action**: Keep all three but clarify docstrings. USGS is the detailed earthquake tool; GDACS/EONET are multi-hazard alert tools. Consider a provider-agnostic wrapper (see Section 2).

---

## 2. Provider-Agnostic Routing Opportunities

These are cases where the LLM must currently know which tool to call for a given data concept, when a single "smart" tool could auto-route based on parameters.

### 2.1 Economic Indicators — HIGH VALUE

**Current state**: 5 tools across 3 providers for economic data:
- `econ_fred_series(series_id)` — US only, requires API key, highest frequency
- `econ_fred_search(query)` — search FRED catalog
- `econ_worldbank_indicator(indicator, country)` — 190+ countries, no key, annual
- `econ_worldbank_search(query)` — search WB catalog
- `econ_imf_data(database, ref_area, indicator)` — 190+ countries, no key, complex params

**Problem**: For "GDP of Germany" the LLM must decide between World Bank (`NY.GDP.MKTP.CD`) and IMF (`NGDP_R_XDC` in IFS). For "US unemployment" it must choose between FRED (`UNRATE`) and World Bank (`SL.UEM.TOTL.ZS`).

**Proposed**: Add a high-level routing tool:

```python
@mcp.tool()
async def indicator(concept: str, country: str = "", years: str = "") -> dict:
    """Economic indicator by concept. Auto-routes to best provider.
    concept: gdp, inflation, unemployment, interest_rate, trade_balance, population, etc.
    country: ISO2/ISO3 code. If US-only indicator, uses FRED. Otherwise World Bank."""
```

**Routing logic**:
| Concept | US → | Non-US → | Fallback → |
|---------|------|----------|------------|
| GDP | FRED (`GDP`) | World Bank (`NY.GDP.MKTP.CD`) | IMF IFS |
| CPI/Inflation | FRED (`CPIAUCSL`) | World Bank (`FP.CPI.TOTL.ZG`) | IMF IFS |
| Unemployment | FRED (`UNRATE`) | World Bank (`SL.UEM.TOTL.ZS`) | — |
| Interest Rate | FRED (`DFF`) | IMF IFS | — |
| Population | — | World Bank (`SP.POP.TOTL`) | — |

**Keep underlying tools** for power users who want specific series IDs. The router is an additional convenience layer.

### 2.2 Disaster / Natural Events — MEDIUM VALUE

**Current state**: 3 tools, 3 providers:
- `disaster_get_earthquakes` — USGS, earthquakes only, high detail
- `disaster_get_disasters` — GDACS, multi-hazard, alert-level
- `disaster_get_natural_events` — NASA EONET, multi-hazard, event-tracking

**Proposed**: Add a unified entry point:

```python
@mcp.tool()
async def hazard_alerts(hazard: str = "", days: int = 7,
                        min_severity: str = "") -> dict:
    """Natural hazard alerts. Auto-selects best source.
    hazard: earthquake, flood, cyclone, volcano, wildfire, drought, all.
    For earthquakes: routes to USGS (detailed). Others: GDACS + EONET."""
```

### 2.3 Conflict Events — LOWER VALUE

**Current state**: 2 tools:
- `conflict_ucdp_conflicts(year)` — UCDP, academic, annual, free
- `conflict_acled_events(country, event_type)` — ACLED, real-time, requires API key

**These are complementary** (UCDP is historical/academic, ACLED is real-time/operational). A router adds marginal value since use cases differ. Keep as-is.

---

## 3. Utility MCP Assessment

### Current Architecture (4 MCP server processes)

| Server | Transport | Package | Purpose |
|--------|-----------|---------|---------|
| **trading** | streamable-http :8071 | FastMCP (Python) | Store + 9 data domains |
| **filesystem** | stdio | `@modelcontextprotocol/server-filesystem` | File read/write in `~/TradeAssistant_Data/files/` |
| **memory** | stdio | `@modelcontextprotocol/server-memory` | Knowledge graph (entities, relations) |
| **sqlite** | stdio | `mcp-sqlite` | SQL queries on `data.db` |

### Overlap with Trading Store?

| Capability | Store Already Does | Utility MCP Adds |
|------------|-------------------|------------------|
| Document storage | Profiles (structured JSON, git-tracked) | Arbitrary files (exports, reports, PDFs) |
| Knowledge persistence | Notes (per-user, MongoDB) | Entity graph (cross-session, relational) |
| Structured queries | MongoDB aggregation pipeline | SQL (joins, GROUP BY, ad-hoc analytics) |

**Verdict**: **No functional overlap.** The store handles domain-specific structured data (profiles, snapshots, notes). The utility MCPs handle ad-hoc user data (files, knowledge, SQL). Keep separate.

### Could We Drop Any?

| MCP | Drop? | Rationale |
|-----|-------|-----------|
| **filesystem** | No | Needed for user exports, report generation, document storage |
| **memory** | Maybe | Lowest usage; knowledge could be stored as notes. But memory's entity-relation graph is better for connecting concepts across conversations. **Keep for now, monitor usage.** |
| **sqlite** | No | SQL is the right tool for ad-hoc structured queries. MongoDB aggregation is powerful but SQL is more natural for many analyses. |

---

## 4. Tool Count Optimization Summary

### Before (current)

| Namespace | Tools | External APIs |
|-----------|-------|---------------|
| store | 24 | MongoDB |
| econ | 5 | FRED, World Bank, IMF |
| weather | 6 | Open-Meteo, NOAA, USGS, USDM |
| disaster | 3 | USGS, GDACS, NASA |
| conflict | 7 | UCDP, ACLED, OpenSanctions, World Bank, UNHCR, HDX, ReliefWeb |
| agri | 4 | FAOSTAT, USDA NASS |
| commodity | 2 | UN Comtrade, EIA |
| health | 4 | WHO, disease.sh, OpenFDA |
| politics | 7 | Wikidata, EU Parliament, Google Civic, ReliefWeb |
| transport | 5 | OpenSky, AIS, Cloudflare, RIPE |
| **Total** | **67** | **25+ APIs** |

### After (proposed)

| Change | Tools Removed | Tools Added | Net |
|--------|--------------|-------------|-----|
| Remove `election_reports` (ReliefWeb dupe) | -1 | — | -1 |
| Remove `military_spending` (WB wrapper) | -1 | — | -1 |
| Add `indicator()` router | — | +1 | +1 |
| Add `hazard_alerts()` router | — | +1 | +1 |
| **Net change** | **-2** | **+2** | **0** |

Tool count stays the same, but **LLM decision quality improves** — the routers handle provider selection that the LLM currently guesses at.

---

## 5. Recommended Actions

### Immediate (P0)

1. **Remove `politics_election_reports`** from `elections_server.py` — pure duplication
2. **Remove `conflict_military_spending`** from `conflict_server.py` — add indicator code to `worldbank_indicator` docstring instead

### Short-term (P1)

3. **Add `econ_indicator()` router** in `macro_server.py` — auto-routes GDP/CPI/unemployment to best provider by country
4. **Add `disaster_hazard_alerts()` router** in `disasters_server.py` — unified entry for multi-hazard queries

### Monitor (P2)

5. **Track memory MCP usage** — if rarely used, consider dropping in favor of store notes
6. **Add docstring disambiguation** to disaster tools — make it clear when to use USGS vs GDACS vs EONET

---

## 6. Provider-Agnostic Design Pattern

For future tools, follow this pattern:

```python
# High-level router (provider-agnostic, LLM-friendly)
@mcp.tool()
async def indicator(concept: str, country: str = "", years: str = "") -> dict:
    """Economic indicator by concept. Auto-routes to best provider."""
    provider = _select_provider(concept, country)
    return await provider.fetch(concept, country, years)

# Low-level tools (provider-specific, power-user access)
@mcp.tool()
async def fred_series(series_id: str, ...) -> dict: ...
@mcp.tool()
async def worldbank_indicator(indicator: str, ...) -> dict: ...
```

**Principle**: Present **concepts** at the top level, **providers** underneath. The LLM asks for "GDP of Germany" → the tool figures out World Bank is the right source. Power users can still call `fred_series("GDP")` directly.

This pattern scales: as new providers are added (Eurostat, OECD, ECB), the router absorbs them without increasing tool count or LLM decision burden.
