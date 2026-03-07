# Multi-Agent Architecture — TradingAssistant on LibreChat

## Goal

Keep main context minimal. Route all 65+ MCP tools through 5 specialized sub-agents
instead of dumping every tool into one conversation. LLM picks from ~5 agent descriptions
instead of ~65 tool descriptions.

**Requires**: LibreChat >= 0.8.1 (Agent Handoffs) or >= 0.7.8 (Agent Chain).

---

## Context Flow

```
User
 └─► Main Agent  (no MCPs, delegates via agentsTool / handoffs)
      │
      ├─► 📊 Market Agent     → trading MCP (store_*, econ_*, commodity_*)
      │                          + yahoo-finance MCP + prediction-market MCP
      │
      ├─► 🌍 OSINT Agent      → trading MCP (disaster_*, conflict_*, weather_*,
      │                          health_*, politics_*, transport_*, agri_*)
      │                          + GDELT Cloud MCP
      │
      ├─► 📰 Signals Agent    → rss MCP + reddit MCP + hn MCP
      │                          + crypto-feargreed MCP
      │
      ├─► 🗄️  Data Agent       → filesystem MCP + memory MCP + sqlite MCP
      │
      └─► 📝 Notes Agent      → trading MCP (store_save_note, store_get_notes,
                                  store_update_note, store_delete_note,
                                  store_risk_status)
```

---

## Why This Split

| Problem Today | Multi-Agent Fix |
|--------------|----------------|
| LLM sees 65+ tools → decision paralysis, wrong tool selection | Each agent sees 8–15 tools max in its domain |
| "Get AAPL price" triggers wrong namespace (econ_ instead of future market_) | Market Agent owns all price/trade tools |
| News sentiment + macro data + disaster alerts = context bloat in one turn | Each agent returns compact summary, main stitches |
| MCP failure in one domain blocks entire conversation | Error isolated within sub-agent boundary |

---

## Agent Definitions

### Main Agent (Orchestrator)

| Setting | Value |
|---------|-------|
| MCP servers | **none** |
| Tools | `agentsTool` only (delegates to sub-agents) |
| Model | Best available (Sonnet 4.6 / Opus 4.6) |

**System prompt** (core):

> You are a trading intelligence orchestrator. You have NO direct tool access.
> Delegate ALL data retrieval to specialist agents:
>
> - **market**: Stock prices, economic indicators, commodities, energy, trade flows, predictions
> - **osint**: Weather, disasters, conflicts, health outbreaks, elections, transport, agriculture
> - **signals**: News feeds (RSS, Reddit, HN), crypto sentiment, social signals
> - **data**: File storage, knowledge graph memory, SQL queries on local database
> - **notes**: User's personal notes, plans, watchlists, journal, risk status
>
> Rules:
> 1. Always delegate. Never answer data questions from memory alone.
> 2. Request compact output (JSON/bullets). Raw API dumps waste your context.
> 3. Cap at 2–3 agent hops per user request. Beyond that, rethink the approach.
> 4. When combining data from multiple agents, synthesize — don't just concatenate.
> 5. For multi-step workflows (research → store → analyze), pass minimal context between hops.

---

### Market Agent

**Scope**: Prices, fundamentals, economic indicators, commodities, energy, trade data, prediction markets.

| Setting | Value |
|---------|-------|
| MCP servers | `trading` (filtered to store_*, econ_*, commodity_* namespaces) |
| External MCPs | `yahoo-finance` (Tier 1), `prediction-market` (Tier 1) |
| Model | Sonnet (reasoning needed for indicator routing) |

**Tools available** (~20):
- `econ_indicator` (router), `econ_fred_series`, `econ_fred_search`, `econ_worldbank_indicator`, `econ_worldbank_search`, `econ_imf_data`
- `commodity_trade_flows`, `commodity_energy_series`
- `store_get_profile`, `store_list_profiles`, `store_find_profile`, `store_search_profiles`
- `store_snapshot`, `store_history`, `store_trend`, `store_chart`
- yahoo-finance tools (stock_price, financials, options, news)
- prediction-market tools (polymarket, predictit, kalshi)

**System prompt** (core):

> You are the Market Agent for a trading intelligence platform.
> You handle: stock prices, economic indicators, commodities, energy data, trade flows,
> and prediction markets.
>
> For economic indicators, prefer the `indicator()` router — it auto-selects the best
> data source (FRED for US, World Bank for international, IMF fallback).
> For stock data, use yahoo-finance tools.
> For prediction odds, use prediction-market tools.
>
> Return compact JSON: {metric, value, source, period, trend?}.
> Never return raw API responses — extract and summarize.

**Output contract**:
```json
{"metric": "GDP", "country": "US", "value": "28.78T", "period": "2024-Q4",
 "source": "fred", "trend": "+2.8% YoY"}
```

---

### OSINT Agent

**Scope**: Geopolitical intelligence — weather, disasters, conflicts, health, elections, transport, agriculture.

| Setting | Value |
|---------|-------|
| MCP servers | `trading` (filtered to disaster_*, conflict_*, weather_*, health_*, politics_*, transport_*, agri_* namespaces) |
| External MCPs | `gdelt-cloud` (Tier 1 cloud endpoint) |
| Model | Haiku (mostly lookups, less reasoning needed) |

**Tools available** (~25):
- `disaster_hazard_alerts` (router), `disaster_get_earthquakes`, `disaster_get_disasters`, `disaster_get_natural_events`
- `conflict_ucdp_conflicts`, `conflict_acled_events`, `conflict_search_sanctions`, `conflict_reliefweb_reports`, `conflict_unhcr_population`, `conflict_hdx_search`
- `weather_forecast`, `weather_historical_weather`, `weather_flood_forecast`, `weather_space_weather`, `weather_streamflow`, `weather_drought`
- `health_who_indicator`, `health_disease_outbreaks`, `health_disease_tracker`, `health_fda_adverse_events`
- `politics_global_elections`, `politics_heads_of_state`, `politics_eu_parliament_meps`, `politics_eu_parliament_votes`, `politics_us_representatives`, `politics_us_voter_info`
- `transport_flights_in_area`, `transport_flight_history`, `transport_vessels_in_area`, `transport_internet_traffic`, `transport_ripe_probes`
- `agri_fao_datasets`, `agri_fao_data`, `agri_usda_crop`, `agri_usda_crop_progress`
- GDELT tools (news events, entity sentiment)

**System prompt** (core):

> You are the OSINT Agent for a trading intelligence platform.
> You monitor: natural disasters, armed conflicts, disease outbreaks, elections,
> shipping/aviation, weather events, agricultural conditions, internet infrastructure.
>
> For hazards, prefer the `hazard_alerts()` router — it auto-selects USGS for earthquakes,
> GDACS + NASA EONET for other hazards.
> For news/events sentiment, use GDELT tools.
> For sanctions/persons, use search_sanctions.
>
> Return compact alerts: {event_type, severity, location, summary, source, timestamp}.
> Flag anything above "medium" severity prominently.

**Output contract**:
```json
{"event_type": "earthquake", "severity": "high", "location": "Turkey",
 "summary": "M6.2 earthquake near Hatay, tsunami: no", "source": "usgs",
 "timestamp": "2026-03-07T14:22:00Z"}
```

---

### Signals Agent

**Scope**: Social sentiment, news feeds, crypto sentiment — the "pulse" layer.

| Setting | Value |
|---------|-------|
| MCP servers | `rss` (Tier 1), `reddit` (Tier 1) |
| External MCPs | `hn` (Tier 2), `crypto-feargreed` (Tier 2) |
| Model | Haiku (simple retrieval + light summarization) |

**Tools available** (~8–12):
- RSS/RSSHub tools (SEC filings, LinkedIn, GitHub trending, PH, YC jobs)
- Reddit tools (frontpage, hot/new/top, subreddit, comments)
- Hacker News tools (stories, search)
- Crypto Fear & Greed index

**System prompt** (core):

> You are the Signals Agent for a trading intelligence platform.
> You scan: RSS feeds (SEC filings, LinkedIn, GitHub), Reddit (wallstreetbets, stocks,
> cryptocurrency), Hacker News, and crypto sentiment.
>
> Prioritize: SEC filings > earnings-related Reddit chatter > HN tech launches > general.
> For crypto, always include the Fear & Greed index as context.
>
> Return: {signal_type, source, title, summary, sentiment?, relevance: high/medium/low}.
> Filter aggressively — only surface signals with trading relevance.

**Output contract**:
```json
{"signal_type": "sec_filing", "source": "rss/sec", "title": "AAPL 10-Q filed",
 "summary": "Q1 2026 quarterly report", "relevance": "high"}
```

---

### Data Agent

**Scope**: Persistent storage — files, knowledge graph, SQL analytics.

| Setting | Value |
|---------|-------|
| MCP servers | `filesystem`, `memory`, `sqlite` |
| Model | Haiku (structured I/O, no reasoning needed) |

**Tools available** (~10):
- filesystem: read_file, write_file, list_directory, search_files, etc.
- memory: create_entity, create_relation, search_nodes, open_nodes, etc.
- sqlite: query, execute, list_tables, describe_table, etc.

**System prompt** (core):

> You are the Data Agent for a trading intelligence platform.
> You manage: file storage (exports, reports), knowledge graph (entity relationships),
> and SQL database (structured analytics).
>
> Files are stored in ~/TradeAssistant_Data/files/ and git-synced every 15 minutes.
> Memory stores entity-relation graphs across conversations.
> SQLite is for ad-hoc structured queries and analytics.
>
> Return: operation result + confirmation. For queries, return data as compact JSON table.

---

### Notes Agent

**Scope**: Per-user notes, plans, watchlists, journal, risk gate.

| Setting | Value |
|---------|-------|
| MCP servers | `trading` (filtered to store_save_note, store_get_notes, store_update_note, store_delete_note, store_risk_status) |
| Model | Haiku (CRUD operations only) |

**Tools available** (5):
- `store_save_note`, `store_get_notes`, `store_update_note`, `store_delete_note`
- `store_risk_status`

**System prompt** (core):

> You are the Notes Agent. You manage the user's personal notes, trading plans,
> watchlists, and journal entries. You also check risk status.
>
> Note kinds: note, plan, watchlist, journal.
> Always confirm saves/updates/deletes. For risk_status, surface remaining daily actions prominently.

---

## MCP Server Mapping

### Current Architecture (monolith)

```
LibreChat → 1 "trading" MCP connection → combined_server.py (65+ tools)
          → 1 "filesystem" MCP → stdio
          → 1 "memory" MCP → stdio
          → 1 "sqlite" MCP → stdio
```

### Multi-Agent Architecture (split)

**Option A: Single trading MCP, tool filtering per agent** (simpler)

The combined_server.py stays as-is. Each LibreChat agent is configured to use the
same `trading` MCP connection but with tool filtering via the agent's `allowedTools`
or equivalent setting (LibreChat agent config allows selecting which tools from
an MCP server are available to a given agent).

```
trading MCP (:8071) ←── Market Agent (store_*, econ_*, commodity_* tools only)
       ↑            ←── OSINT Agent (disaster_*, conflict_*, weather_*, ... tools only)
       ↑            ←── Notes Agent (store_save_note, store_get_notes, ... only)
```

**Option B: Split into multiple MCP processes** (more isolation, more ops)

```
market MCP  (:8071) ←── Market Agent
osint MCP   (:8072) ←── OSINT Agent
store MCP   (:8073) ←── Notes Agent + Market Agent (profiles)
```

**Recommendation**: **Option A** — single trading MCP process, filter at the agent level.
Splitting into multiple processes adds operational complexity (3 supervisord services
instead of 1) with minimal benefit since all servers share the same Python process
and MongoDB connection anyway.

---

## Multi-Step Orchestration Examples

### Example 1: "What's happening with AAPL?"

```
Main:
  1. → market("AAPL stock price and fundamentals")
       Returns: {price: 198.50, pe: 31.2, eps: 6.40, trend: "+3.2% 1mo"}
  2. → signals("AAPL SEC filings and Reddit sentiment")
       Returns: {filing: "10-Q filed 2026-02-28", reddit: "bullish, 72% positive"}
  3. → Synthesize and reply to user
```

### Example 2: "Any supply chain risks for semiconductor stocks?"

```
Main:
  1. → osint("Taiwan strait tensions, shipping disruptions, earthquake activity near TSMC")
       Returns: {conflict: "low", shipping: "normal", earthquake: "M3.1 Hualien, minor"}
  2. → market("TSMC, ASML, NVDA stock trends + semiconductor commodity prices")
       Returns: {tsmc: "+1.2%", asml: "-0.5%", nvda: "+4.8%", silicon: "stable"}
  3. → Synthesize risk assessment for user
```

### Example 3: "Save a watchlist for European energy stocks"

```
Main:
  1. → market("European energy stocks: Shell, TotalEnergies, BP, Equinor prices")
       Returns: {shel: 28.50, tte: 55.20, bp: 5.80, eqnr: 25.10}
  2. → notes("save watchlist: European Energy - SHEL, TTE, BP, EQNR with current prices")
       Returns: {saved: true, note_id: "abc123"}
  3. → Reply to user with confirmation
```

### Rules for Chains

- Sub-agents return **compact structured output** — raw API dumps are forbidden
- Main extracts and forwards **minimal slice** of prior result to next agent
- **Cap at 3 hops** — beyond that, rethink (maybe one agent needs more tools)
- If a task needs tools from 2 domains (e.g., market data + OSINT), main calls both agents and synthesizes — don't try to give one agent everything

---

## Agent Configuration in LibreChat

Agents are configured via LibreChat UI (Admin Panel → Agents), not in `librechat.yaml`.
Each agent needs:

1. **Name** — short, used as routing key by main agent
2. **Description** — precise scope (this is the main LLM's routing signal)
3. **System prompt** — task-focused, includes output contract
4. **Model** — Haiku for lookups, Sonnet for reasoning
5. **MCP servers** — selected per agent from the global mcpServers list
6. **Tool selection** — which tools from each MCP server are enabled

### librechat.yaml MCP Changes

The `mcpServers` section in `librechat.yaml` defines **available** MCP servers.
Agent-level tool selection happens in the agent config UI.

Add Tier 1 external MCPs to `librechat.yaml`:

```yaml
mcpServers:
  # ... existing utility + trading MCPs ...

  # ── Tier 1 External MCPs ────────────────────
  yahoo-finance:
    command: pip
    args: ["run", "yahoo-finance-mcp"]
    serverInstructions: "Stock data: OHLCV, financials, options chains, news. Zero auth."

  gdelt-cloud:
    type: streamable-http
    url: https://gdelt-cloud-mcp.fastmcp.app/mcp
    serverInstructions: "Global news events, entity sentiment, 65 languages, 150 countries."

  prediction-markets:
    command: npx
    args: ["-y", "prediction-markets-mcp"]
    serverInstructions: "Prediction market odds: Polymarket, PredictIt, Kalshi. Read-only."

  rss:
    command: node
    args: ["__HOME__/mcps/node_modules/rss-mcp/index.js"]
    serverInstructions: "RSS/Atom feeds + RSSHub routes (SEC filings, LinkedIn, GitHub trending)."

  reddit:
    command: uvx
    args: ["mcp-server-reddit"]
    serverInstructions: "Reddit read-only: frontpage, subreddits, hot/new/top, comments."
```

---

## Latency & Cost Analysis

| Pattern | LLM Calls | Latency | Cost |
|---------|-----------|---------|------|
| **Monolith** (today) | 1 call, 65+ tools in context | Fastest single-turn | Highest per-token (large tool schema) |
| **Multi-agent** (proposed) | 2–4 calls (main + 1–3 sub-agents) | +1–3s per delegation | Lower per-agent (smaller tool schema) |

**Net effect**: Slightly higher latency but **better accuracy** (less tool confusion) and
**lower total tokens** (each agent sees only its tools, not all 65+).

For a Haiku sub-agent doing a simple lookup: ~0.5s overhead.
For a Sonnet sub-agent doing indicator routing: ~1.5s overhead.

---

## Migration Path

### Phase 1: Create agents in LibreChat UI (no code changes)

1. Create 5 agents (market, osint, signals, data, notes) in LibreChat admin
2. Assign MCP servers and tool selections per agent
3. Create main orchestrator agent with agentsTool
4. Test with real user queries

### Phase 2: Add Tier 1 external MCPs (config changes only)

1. Add `yahoo-finance`, `gdelt-cloud`, `prediction-markets`, `rss`, `reddit` to `librechat.yaml`
2. Assign to appropriate agents (market, osint, signals)
3. No Python code changes needed

### Phase 3: Optimize based on usage (later)

1. Track which agents get called most → optimize their model choice
2. If an agent is rarely used, consider merging it into another
3. If an agent is overloaded (too many tools), consider splitting it

---

## Comparison to Reference Architecture

| Reference Sketch | Our Adaptation |
|-----------------|---------------|
| Research Agent (library-first) | Split into Market + OSINT + Signals (domain separation more valuable than cache-first pattern for real-time data) |
| Files Agent | Data Agent (filesystem + memory + sqlite) |
| Comms Agent (gmail, gcal) | Not needed (no comms integration) |
| Data Agent (mongodb, postgres) | Notes Agent (store notes + risk) — MongoDB access is via trading MCP, not direct |
| Dev Agent (mkbc, replicate) | Not needed (no code gen/image gen in trading context) |
| Library-first pattern | Not applicable — trading data is real-time, caching stale data is counterproductive. Instead: snapshot to MongoDB for historical queries. |
| Shared memory: none | Same — main passes minimal context between hops |
| Model per agent | Same — Haiku for lookups, Sonnet for reasoning |

### Key Difference: Real-Time vs. Library-First

The reference architecture's "check library first, fetch live on miss" pattern doesn't
fit trading. Stock prices, disaster alerts, and conflict events must be **live by default**.

Our equivalent: agents always fetch live, then optionally `store_snapshot()` for
historical tracking. The store is for **time series**, not caching.
