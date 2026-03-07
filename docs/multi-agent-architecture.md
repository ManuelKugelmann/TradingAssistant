# Multi-Agent Architecture — TradingAssistant on LibreChat

## Goal

Keep main context minimal. Route all 65+ MCP tools through 5 specialized sub-agents
instead of dumping every tool into one conversation. LLM picks from ~5 agent handoff
targets instead of ~65 tool descriptions.

**Requires**: LibreChat >= 0.8.1 (Agent Handoffs).

---

## How LibreChat Agent Delegation Actually Works

There is **no tool called `agentsTool`**. LibreChat has two delegation mechanisms:

### Handoff Edges (v0.8.1+) — Primary mechanism

Agents are configured with **edges** to other agents in the Agent Builder UI.
When Agent A has an edge to Agent B, LibreChat auto-generates a handoff tool
that transfers control. Uses LangGraph under the hood. Transitive handoffs
supported (A → B → C). Recursive and parallel handoffs available.

**Caveat**: Handoff reliability is ~60% — the receiving agent may not fully
recognize the context switch. Mitigate by appending explicit routing instructions
to agent system prompts.

### Agent Chain / Mixture-of-Agents (Beta)

Enabled via `chain` capability in `librechat.yaml`. Chains up to 10 agents
sequentially — each receives the previous agent's output. Configured in
Advanced Settings per agent. Better for deterministic pipelines.

### Where Agents Live

| What | Where |
|------|-------|
| MCP server definitions | `librechat.yaml` → `mcpServers` |
| Agent definitions | Agent Builder UI → stored in **MongoDB** |
| MCP → Agent binding | Agent Builder UI → per-agent tool selection |
| Tool enable/disable | Agent Builder UI → expand MCP server → toggle individual tools |

Agents are **not** defined in YAML. They are UI-configured and DB-stored.

---

## Context Flow

```
User
 └─► Main Agent  (no MCPs, handoff edges to 5 sub-agents)
      │
      ├──edge──► market     → trading MCP (store_*, econ_*, commodity_*)
      │                       + yahoo-finance MCP + prediction-market MCP
      │
      ├──edge──► osint      → trading MCP (disaster_*, conflict_*, weather_*,
      │                       health_*, politics_*, transport_*, agri_*)
      │                       + GDELT Cloud MCP
      │
      ├──edge──► signals    → rss MCP + reddit MCP + hn MCP
      │                       + crypto-feargreed MCP
      │
      ├──edge──► data       → filesystem MCP + memory MCP + sqlite MCP
      │
      └──edge──► notes      → trading MCP (store notes + risk tools only)
```

Each edge auto-generates a handoff tool in the main agent's context.
Main sees 5 handoff tools, not 65+ data tools.

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
| Handoff edges | market, osint, signals, data, notes |
| Model | Best available (Sonnet 4.6 / Opus 4.6) |

**System prompt** (core):

> You are a trading intelligence orchestrator. You have NO direct data tools.
> You delegate to specialist agents via handoffs. Available agents:
>
> - **market** — Stock prices, economic indicators, commodities, energy, trade flows, prediction market odds
> - **osint** — Weather, disasters, armed conflicts, disease outbreaks, elections, shipping/aviation, agriculture, internet infra
> - **signals** — RSS feeds (SEC filings, LinkedIn), Reddit, Hacker News, crypto sentiment
> - **data** — File storage, knowledge graph, SQL queries on local database
> - **notes** — User's personal notes, plans, watchlists, journal, risk status
>
> Rules:
> 1. Always hand off for data. Never answer data questions from memory alone.
> 2. When handing off, be explicit about what you need: "Get AAPL price and 1-month trend."
> 3. Cap at 2–3 handoffs per user request. Beyond that, collapse into fewer agents.
> 4. When combining data from multiple agents, synthesize — don't just concatenate.
> 5. For multi-step workflows (research → store → analyze), pass minimal context between hops.
> 6. If a handoff fails or returns unclear results, retry once with a more specific request before falling back to the user.

---

### Market Agent

**Scope**: Prices, fundamentals, economic indicators, commodities, energy, trade data, prediction markets.

| Setting | Value |
|---------|-------|
| MCP servers | `trading` (enable only: store_*, econ_*, commodity_* tools) |
| External MCPs | `yahoo-finance`, `prediction-markets` |
| Model | Sonnet (reasoning needed for indicator routing) |
| Handoff edges | back to main (return results) |

**Tools enabled** (~20):
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
> For economic indicators, prefer `econ_indicator()` — it auto-selects the best
> data source (FRED for US, World Bank for international, IMF fallback).
> For stock data, use yahoo-finance tools.
> For prediction odds, use prediction-market tools.
>
> Return compact JSON. Never return raw API responses — extract and summarize.
> Format: {metric, value, source, period, trend?}.

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
| MCP servers | `trading` (enable only: disaster_*, conflict_*, weather_*, health_*, politics_*, transport_*, agri_* tools) |
| External MCPs | `gdelt-cloud` |
| Model | Haiku (mostly lookups, less reasoning needed) |
| Handoff edges | back to main |

**Tools enabled** (~30):
- `disaster_hazard_alerts` (router), `disaster_get_earthquakes`, `disaster_get_disasters`, `disaster_get_natural_events`
- `conflict_ucdp_conflicts`, `conflict_acled_events`, `conflict_search_sanctions`, `conflict_reliefweb_reports`, `conflict_unhcr_population`, `conflict_hdx_search`
- `weather_forecast`, `weather_historical_weather`, `weather_flood_forecast`, `weather_space_weather`, `weather_streamflow`, `weather_drought`
- `health_who_indicator`, `health_disease_outbreaks`, `health_disease_tracker`, `health_fda_adverse_events`
- `politics_global_elections`, `politics_heads_of_state`, `politics_eu_parliament_meps`, `politics_eu_parliament_votes`, `politics_us_representatives`, `politics_us_voter_info`
- `transport_flights_in_area`, `transport_flight_history`, `transport_vessels_in_area`, `transport_internet_traffic`, `transport_ripe_probes`
- `agri_fao_datasets`, `agri_fao_data`, `agri_usda_crop`, `agri_usda_crop_progress`
- GDELT Cloud tools (news events, entity sentiment)

**System prompt** (core):

> You are the OSINT Agent for a trading intelligence platform.
> You monitor: natural disasters, armed conflicts, disease outbreaks, elections,
> shipping/aviation, weather events, agricultural conditions, internet infrastructure.
>
> For hazards, prefer `disaster_hazard_alerts()` — it auto-selects USGS for earthquakes,
> GDACS + NASA EONET for other hazards.
> For news/events sentiment, use GDELT tools.
> For sanctions/persons, use search_sanctions.
>
> Return compact alerts. Format: {event_type, severity, location, summary, source, timestamp}.
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
| MCP servers | `rss`, `reddit` |
| External MCPs | `hn` (Tier 2), `crypto-feargreed` (Tier 2) |
| Model | Haiku (simple retrieval + light summarization) |
| Handoff edges | back to main |

**Tools enabled** (~8–12):
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
| Handoff edges | back to main |

**Tools enabled** (~10):
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
| MCP servers | `trading` (enable only: store_save_note, store_get_notes, store_update_note, store_delete_note, store_risk_status) |
| Model | Haiku (CRUD operations only) |
| Handoff edges | back to main |

**Tools enabled** (5):
- `store_save_note`, `store_get_notes`, `store_update_note`, `store_delete_note`
- `store_risk_status`

**System prompt** (core):

> You are the Notes Agent. You manage the user's personal notes, trading plans,
> watchlists, and journal entries. You also check risk status.
>
> Note kinds: note, plan, watchlist, journal.
> Always confirm saves/updates/deletes. For risk_status, surface remaining daily actions prominently.

---

## MCP Server Configuration

### librechat.yaml — MCP Servers (global availability)

All MCP servers are defined globally. Use `chatMenu: false` to hide servers
from the general chat menu and restrict them to agent-only access.

```yaml
mcpServers:

  # ── Existing ────────────────────────────────
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "__HOME__/TradeAssistant_Data/files/"]
    chatMenu: false                    # Agent-only (Data Agent)

  memory:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-memory"]
    env:
      MEMORY_FILE_PATH: __HOME__/TradeAssistant_Data/memory.jsonl
    chatMenu: false                    # Agent-only (Data Agent)

  sqlite:
    command: npx
    args: ["-y", "mcp-sqlite", "__HOME__/TradeAssistant_Data/data.db"]
    chatMenu: false                    # Agent-only (Data Agent)

  trading:
    type: streamable-http
    url: http://localhost:8071/mcp
    chatMenu: false                    # Agent-only (Market, OSINT, Notes Agents)
    headers:
      X-User-ID: "{{LIBRECHAT_USER_ID}}"
      X-User-Email: "{{LIBRECHAT_USER_EMAIL}}"
      X-Broker-Key: "{{BROKER_API_KEY}}"
      X-Broker-Secret: "{{BROKER_API_SECRET}}"
      X-Broker-Name: "{{BROKER_NAME}}"
      X-Risk-Daily-Limit: "{{RISK_DAILY_LIMIT}}"
      X-Risk-Live-Trading: "{{RISK_LIVE_TRADING}}"
    customUserVars:
      BROKER_API_KEY:
        title: "Broker API Key"
        description: "Your trading broker API key"
      BROKER_API_SECRET:
        title: "Broker API Secret"
        description: "Your trading broker API secret"
      BROKER_NAME:
        title: "Broker Name"
        description: "alpaca, ibkr, binance, etc."
      RISK_DAILY_LIMIT:
        title: "Daily Action Limit"
        description: "Max trading actions per day (default: 50)"
      RISK_LIVE_TRADING:
        title: "Enable Live Trading"
        description: "Set to 'yes' to allow real trades. Blank = dry-run."

  # ── Tier 1 External MCPs ────────────────────

  yahoo-finance:
    command: python
    args: ["-m", "yahoo_finance_mcp"]
    chatMenu: false                    # Agent-only (Market Agent)
    serverInstructions: "Stock data: OHLCV, financials, options, news. Zero auth."

  gdelt-cloud:
    type: streamable-http
    url: https://gdelt-cloud-mcp.fastmcp.app/mcp
    chatMenu: false                    # Agent-only (OSINT Agent)
    serverInstructions: "Global news events, entity sentiment, 65 languages, 150 countries."

  prediction-markets:
    command: npx
    args: ["-y", "prediction-markets-mcp"]
    chatMenu: false                    # Agent-only (Market Agent)
    serverInstructions: "Prediction market odds: Polymarket, PredictIt, Kalshi. Read-only."

  rss:
    command: node
    args: ["__HOME__/mcps/node_modules/rss-mcp/index.js"]
    chatMenu: false                    # Agent-only (Signals Agent)
    serverInstructions: "RSS/Atom + RSSHub routes (SEC filings, LinkedIn, GitHub trending)."

  reddit:
    command: uvx
    args: ["mcp-server-reddit"]
    chatMenu: false                    # Agent-only (Signals Agent)
    serverInstructions: "Reddit read-only: frontpage, subreddits, hot/new/top, comments."
```

### librechat.yaml — Agents Endpoint Config

```yaml
endpoints:
  agents:
    recursionLimit: 25
    maxRecursionLimit: 50
    capabilities:
      - tools
      - actions
      - artifacts
      - chain                          # Beta: MoA sequential pipelines
    allowedProviders:
      - anthropic
      - openAI
      # Add other providers as needed
```

### MCP → Agent Binding (Agent Builder UI)

After deploying the YAML config, create agents in the Agent Builder UI:

| Agent | MCP Servers to Add | Tools to Enable |
|-------|--------------------|-----------------|
| **main** | (none) | Handoff edges only: market, osint, signals, data, notes |
| **market** | trading, yahoo-finance, prediction-markets | store_*, econ_*, commodity_* from trading; all from yahoo-finance & predictions |
| **osint** | trading, gdelt-cloud | disaster_*, conflict_*, weather_*, health_*, politics_*, transport_*, agri_* from trading; all from gdelt-cloud |
| **signals** | rss, reddit | All tools from both |
| **data** | filesystem, memory, sqlite | All tools from all three |
| **notes** | trading | store_save_note, store_get_notes, store_update_note, store_delete_note, store_risk_status only |

---

## Handoff Reliability Mitigation

Handoff success rate is ~60%. Strategies to improve:

### 1. Explicit routing rules in main agent system prompt

```
When handing off to the market agent, ALWAYS format your request as:
"Retrieve: [specific data point]. Format: [expected output]."
Do not hand off vague questions — decompose first.
```

### 2. Sub-agent context anchoring

Each sub-agent's system prompt starts with a strong identity anchor:

```
You are the [X] Agent. You were called by the orchestrator to handle a specific request.
The request is in the user message. Execute it using your tools and return results.
Do NOT ask clarifying questions — use defaults for missing parameters.
```

### 3. Fallback: Agent Chain for deterministic pipelines

For predictable multi-step flows (e.g., "morning briefing": market → osint → signals),
use Agent Chain instead of handoffs. Chain guarantees sequential execution.

```
Chain: market → osint → signals → main (synthesize)
```

Configure in main agent's Advanced Settings.

### 4. Retry logic in main agent prompt

```
If a handoff returns empty, malformed, or off-topic results, retry ONCE with
a more specific request. If it fails again, tell the user what went wrong
and which data source is unavailable.
```

---

## Multi-Step Orchestration Examples

### Example 1: "What's happening with AAPL?"

```
Main → handoff → market:
  "Retrieve: AAPL stock price (current + 1mo trend) and key fundamentals (PE, EPS)."
  Returns: {price: 198.50, pe: 31.2, eps: 6.40, trend: "+3.2% 1mo"}

Main → handoff → signals:
  "Retrieve: AAPL SEC filings (last 30 days) and Reddit sentiment (r/stocks, r/wallstreetbets)."
  Returns: {filing: "10-Q filed 2026-02-28", reddit: "bullish, 72% positive"}

Main: Synthesize and reply to user.
```

### Example 2: "Any supply chain risks for semiconductor stocks?"

```
Main → handoff → osint:
  "Retrieve: Taiwan strait tensions (ACLED), shipping disruptions (AIS Suez/Strait data),
   earthquake activity near Taiwan (USGS, last 30 days)."
  Returns: {conflict: "low", shipping: "normal", earthquake: "M3.1 Hualien, minor"}

Main → handoff → market:
  "Retrieve: TSMC, ASML, NVDA 1-month price trends + semiconductor commodity prices."
  Returns: {tsmc: "+1.2%", asml: "-0.5%", nvda: "+4.8%", silicon: "stable"}

Main: Synthesize risk assessment.
```

### Example 3: "Morning briefing" (deterministic → use Chain)

```
Agent Chain configured in main's Advanced Settings:
  1. market → "Top 5 movers in S&P 500 today, VIX level, prediction market highlights"
  2. osint  → "Any severity >= medium hazards, conflicts, or health alerts in last 24h"
  3. signals → "Top 5 SEC filings, Reddit trending tickers, crypto Fear & Greed index"
  4. main   → Synthesize into structured briefing
```

### Rules for Handoff Chains

- Sub-agents return **compact structured output** — raw API dumps are forbidden
- Main extracts and forwards **minimal slice** of prior result to next agent
- **Cap at 3 handoffs** — beyond that, collapse into fewer agents
- If a task needs tools from 2 domains (market data + OSINT), main hands off to each separately and synthesizes — don't try to give one agent everything

---

## Architecture Options

### Option A: Single trading MCP, tool filtering per agent (recommended)

The combined_server.py stays as-is (one process, one port). Each LibreChat agent
enables only the tools it needs from the trading MCP in the Agent Builder UI.

```
trading MCP (:8071) ←── Market Agent (store_*, econ_*, commodity_* tools)
       ↑            ←── OSINT Agent (disaster_*, conflict_*, weather_*, ... tools)
       ↑            ←── Notes Agent (store_save_note, ... tools)
```

**Pros**: One supervisord service, one MongoDB connection, one port.
**Cons**: All tools still load in one Python process (but tool filtering happens at LLM level).

### Option B: Split into multiple MCP processes

```
market MCP  (:8071) ←── Market Agent
osint MCP   (:8072) ←── OSINT Agent
store MCP   (:8073) ←── Notes Agent + Market Agent (profiles)
```

**Pros**: True process isolation, independent restarts.
**Cons**: 3 supervisord services, 3 ports, shared MongoDB pool splits.

**Recommendation**: **Option A**. Split only if a single domain server causes crashes
that affect others.

---

## Latency & Cost Analysis

| Pattern | LLM Calls | Latency | Token Efficiency |
|---------|-----------|---------|-----------------|
| **Monolith** (today) | 1 call, 65+ tools in context | Fastest single-turn | Worst (huge tool schema in every call) |
| **Multi-agent handoffs** | 2–4 calls (main + 1–3 sub-agents) | +1–3s per handoff | Best (each agent sees only its tools) |
| **Agent Chain** | N+1 calls (N agents + main synthesis) | Deterministic, pipelined | Good (sequential, no wasted handoff overhead) |

**Net effect**: Slightly higher latency but **better accuracy** (less tool confusion) and
**lower total tokens** (each agent sees 5–20 tools, not 65+).

Haiku sub-agent lookup: ~0.5s overhead per handoff.
Sonnet sub-agent reasoning: ~1.5s overhead per handoff.

---

## Migration Path

### Phase 1: Create agents in LibreChat UI (no code changes)

1. Deploy `librechat.yaml` with `chatMenu: false` on all MCPs
2. Create 5 sub-agents in Agent Builder (market, osint, signals, data, notes)
3. For each: select MCP servers, enable specific tools, set system prompt + model
4. Create main orchestrator agent with handoff edges to all 5
5. Test with real user queries, tune system prompts based on handoff success rate

### Phase 2: Add Tier 1 external MCPs (config changes only)

1. Install external MCPs on Uberspace (`pip install yahoo-finance-mcp`, etc.)
2. Add to `librechat.yaml` (see config above)
3. Assign to appropriate agents in Agent Builder
4. No Python code changes needed

### Phase 3: Optimize based on usage (later)

1. Track which agents get called most → optimize model choice
2. If handoff failure rate is high → switch to Agent Chain for common flows
3. If an agent is rarely used → merge into another
4. If an agent is overloaded (too many tools) → split it

---

## Comparison to Reference Architecture

| Reference Sketch | Our Adaptation | Rationale |
|-----------------|---------------|-----------|
| `agentsTool` delegation | Handoff Edges (v0.8.1) | `agentsTool` doesn't exist in LibreChat; handoff edges are the actual mechanism |
| Research Agent (library-first) | Split into Market + OSINT + Signals | Domain separation > cache-first for real-time trading data |
| Files Agent | Data Agent (filesystem + memory + sqlite) | Same concept, broader scope |
| Comms Agent (gmail, gcal) | Not needed | No comms integration in trading stack |
| Data Agent (mongodb, postgres) | Notes Agent (store notes + risk) | MongoDB access via trading MCP, not direct |
| Dev Agent (mkbc, replicate) | Not needed | No code gen/image gen in trading context |
| Library-first pattern | Live-first, snapshot for history | Trading data must be fresh; store is for time series, not caching |
| Shared memory: none | Same | Main passes minimal context between handoffs |
| Model per agent | Same | Haiku for lookups, Sonnet for reasoning |

### Key Difference: Real-Time vs. Library-First

The reference architecture's "check library first, fetch live on miss" pattern doesn't
fit trading. Stock prices, disaster alerts, and conflict events must be **live by default**.

Our equivalent: agents always fetch live, then optionally `store_snapshot()` for
historical tracking. The store is for **time series**, not caching.
