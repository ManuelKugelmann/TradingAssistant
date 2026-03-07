# Multi-Agent Architecture — TradingAssistant on LibreChat

## Goal

Layered agent pyramid: data scrapers feed storage, reasoning agents analyze and write
back, cross-cutting agents synthesize across domains, autonomous planner/trader operates
on cron, live chat assistant serves the user. Each layer can only see downward.

**Requires**: LibreChat >= 0.8.1 (Agent Handoffs).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  L5  LIVE CHAT ASSISTANT                          (user-facing) │
│       Can hand off to ANY agent below                           │
│       Interactive, conversational, explains reasoning           │
├─────────────────────────────────────────────────────────────────┤
│  L4  CRON PLANNER + EXECUTOR                     (autonomous)   │
│       Research organizer: schedules what to scrape/analyze      │
│       Plan executor / trader: acts on plans via risk gate       │
│       Can use ALL agents below                                  │
├─────────────────────────────────────────────────────────────────┤
│  L3  CROSS-CUTTING REASONING                     (synthesis)    │
│       Reads across ALL domain data in storage                   │
│       Writes: briefings, composite scores, predictions          │
│       Detects cross-domain patterns (disaster → supply chain)   │
├───────────────────────┬─────────────────────────────────────────┤
│  L2  DOMAIN ANALYSTS  │  Per-domain reasoning, summary,        │
│                       │  prediction. Hand off to data agents    │
│  market-analyst       │  for reads, write NOTES back.           │
│  osint-analyst        │                                         │
│  signals-analyst      │  Each analyst owns one domain.          │
├───────────────────────┼─────────────────────────────────────────┤
│  L1  DATA AGENTS      │  Thematic data collection. Scrape MCPs, │
│                       │  own profiles, snapshots, events.       │
│  market-data          │  Also read from storage on request.     │
│  osint-data           │  + filesystem, memory                   │
│  signals-data         │                                         │
├───────────────────────┴─────────────────────────────────────────┤
│  STORAGE              │  Profiles (JSON/git), Snapshots (Mongo), │
│                       │  Notes (Mongo), Plans (Mongo),           │
│                       │  Files, Memory                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer Definitions

### L1 — Data Agents (scrape → store profiles/snapshots/events → return)

Thematic agents that own **all raw data**: profiles, snapshots, and events.
They scrape MCP data sources, write to storage, AND return results to callers.
They also read from storage when asked (history, profiles, events).

Dual behavior is critical:
- On **cron**: scraper stores data, return value is ignored.
- On **interactive handoff**: scraper stores data AND returns it, so the
  calling agent doesn't need to re-read storage (avoids double search).

| Agent | MCP Data Tools | Storage Tools (read + write) | Cron Trigger |
|-------|---------------|------------------------------|-------------|
| **market-data** | `econ_indicator`, `econ_fred_series`, `econ_worldbank_indicator`, `econ_imf_data`, `commodity_trade_flows`, `commodity_energy_series`, yahoo-finance, prediction-markets | `store_snapshot`, `store_event`, `store_history`, `store_trend`, `store_get_profile`, `store_put_profile`, `store_find_profile`, `store_search_profiles`, `store_list_profiles`, `store_chart` | Hourly (prices), daily (indicators) |
| **osint-data** | `disaster_hazard_alerts`, `conflict_acled_events`, `conflict_ucdp_conflicts`, `conflict_reliefweb_reports`, `weather_*`, `health_*`, `politics_*`, `transport_*`, `agri_*`, GDELT Cloud | Same store tools as market-data | Every 6h (disasters, conflicts), daily (weather, agri) |
| **signals-data** | rss, reddit, hn, crypto-feargreed | Same store tools as market-data | Every 2h (RSS/Reddit), every 6h (HN) |

**Owns**: `store_snapshot`, `store_event`, `store_history`, `store_trend`,
`store_get_profile`, `store_put_profile`, `store_find_profile`,
`store_search_profiles`, `store_list_profiles`, `store_nearby`,
`store_recent_events`, `store_archive_snapshot`, `store_archive_history`,
`store_compact`, `store_aggregate`, `store_chart`.

**System prompt pattern** (all L1 agents):

> You are the {domain} data agent. You fetch data, manage profiles/snapshots/events,
> and return results.
>
> **Scraping** (when triggered by cron or handoff):
> 1. Call the data tools listed in your instructions.
> 2. For each result, call `store_snapshot()` or `store_event()` with structured data.
> 3. Update profiles via `store_put_profile()` when entity metadata changes.
> 4. ALSO return the fetched data so the caller can use it immediately.
> 5. If an API fails, store an event with `severity: "low"` noting the failure.
> 6. Return: {fetched: N, stored: N, errors: N, data: [{kind, entity, values...}, ...]}.
>
> **Reading** (when asked for data):
> 1. Use `store_history()`, `store_trend()`, `store_recent_events()` for time series.
> 2. Use `store_get_profile()`, `store_find_profile()` for entity info.
> 3. Use `store_chart()` for visualizations.
> 4. Return the actual data, not just confirmation.
>
> Never analyze or interpret. Store and return raw facts.

**Model**: Haiku (cheapest — no reasoning needed).

---

### L2 — Domain Analysts (read via data agents → reason → write notes)

Per-domain agents that hand off to data agents to read raw data, apply domain
expertise, and write **notes** (analysis, assessments, journal entries) back to storage.
Each analyst owns exactly one domain.

| Agent | Reads Via | Writes (notes) | Reasoning Tasks |
|-------|----------|----------------|-----------------|
| **market-analyst** | Hands off to market-data for history, trends, profiles | `store_save_note(kind=note)`, `store_get_notes`, `store_update_note`, `store_delete_note` | Price trends, indicator divergences, sector rotation, prediction market shifts |
| **osint-analyst** | Hands off to osint-data for events, country snapshots, profiles | Same note tools | Threat assessment, impact scoring, country risk updates, supply chain exposure |
| **signals-analyst** | Hands off to signals-data for signal history, events | Same note tools | Sentiment aggregation, narrative detection, filing significance, social momentum |

**Owns**: `store_save_note`, `store_get_notes`, `store_update_note`, `store_delete_note`.

**System prompt pattern** (all L2 agents):

> You are the {domain} analyst. You analyze data and produce notes.
>
> **Reading data**: Hand off to your data agent ({domain}-data) to fetch
> history, trends, profiles, and events. The data agent returns the actual data.
>
> **Writing analysis**:
> 1. Apply domain expertise: identify trends, anomalies, risk signals.
> 2. Write analysis as notes via `store_save_note(kind="note", tags=["{domain}", ...])`.
> 3. Use `store_get_notes()` to read your own previous analysis for context.
> 4. Return structured output: {domain, key_findings: [...], risk_level, confidence}.
>
> You do NOT call data MCP tools directly. You hand off to the data agent.
> You do NOT fetch live data. You only analyze what data agents have stored.

**Model**: Sonnet (needs reasoning, pattern detection, judgment).

**Handoff edges**: → {domain}-data (for reading storage).

---

### L3 — Cross-Cutting Reasoning (multi-domain → synthesize → write notes)

Reads across ALL domains by handing off to data agents and reading analyst notes.
Detects cross-domain patterns that no single analyst can see. Writes composite
notes (briefings, predictions, assessments).

| Agent | Reads Via | Writes (notes) | Cross-Domain Tasks |
|-------|----------|----------------|-------------------|
| **synthesizer** | Hands off to all 3 data agents for raw data; reads all analyst notes via `store_get_notes` | `store_save_note(kind=note, tags=["briefing"/"prediction"/"alert", ...])` | Morning briefings, cross-domain correlations (earthquake → supply chain → stock impact), composite risk scores, forward-looking predictions |

**Owns**: Same note tools as L2 (`store_save_note`, `store_get_notes`,
`store_update_note`, `store_delete_note`).

**System prompt**:

> You are the Cross-Domain Synthesizer. You read analysis notes from ALL domain
> analysts and raw data from ALL data agents, then detect patterns that span domains.
>
> **Reading**:
> - Hand off to market-data, osint-data, signals-data for raw data as needed.
> - Read analyst notes via `store_get_notes(tag="market"/"osint"/"signals")`.
>
> Examples of cross-domain signals:
> - Earthquake in Taiwan (osint) → TSMC supply risk (market) → semiconductor price impact
> - Drought in US Midwest (osint) → corn/soybean futures (market) → food price inflation
> - Reddit momentum on ticker (signals) + positive earnings (market) → high-conviction signal
> - Conflict escalation (osint) → oil price spike (market) → energy sector rotation
>
> **Writing**:
> 1. Identify cross-domain correlations and causal chains.
> 2. Score composite risk/opportunity for tracked entities.
> 3. Write briefings via `store_save_note(kind="note", tags=["briefing", ...])`.
> 4. Write predictions via `store_save_note(kind="note", tags=["prediction", ...])`.
> 5. Return: {briefing_type, key_signals: [...], predictions: [...], confidence}.

**Model**: Sonnet or Opus (highest reasoning quality needed).

**Handoff edges**: → market-data, osint-data, signals-data (for reading raw storage).

---

### L4 — Cron Planner + Executor (autonomous operations, own plans)

Two roles, can be one or two agents. L4 **owns plans**: it reads and writes
`store_save_note(kind=plan)` and `store_get_notes(kind=plan)`. Plans are the
operational layer — what to research, what to trade, when, and why.

#### Research Organizer

Decides **what** to scrape and analyze, **when**, and **at what depth**.
Reads plans and schedules L1/L2/L3 agents accordingly.

| Capability | How |
|-----------|-----|
| Read/write plans | `store_save_note(kind=plan)`, `store_get_notes(kind=plan)` |
| Schedule scraper runs | Hands off to market-data, osint-data, signals-data |
| Trigger analysis | Hands off to market-analyst, osint-analyst, signals-analyst |
| Request synthesis | Hands off to synthesizer |
| Adjust frequency | Increase scraping frequency for entities with active signals |
| Manage watchlists | Read/write `store_save_note(kind=plan, tags=["watchlist"])` |

**Owns**: `store_save_note(kind=plan)`, `store_get_notes(kind=plan)`,
`store_update_note`, `store_delete_note` (for plan management),
`store_risk_status`.

**System prompt**:

> You are the Research Organizer. You run autonomously on a schedule.
> Your job: ensure data is fresh, analysis is current, and nothing is missed.
>
> You own **plans** — research plans, watchlists, schedules.
>
> Routine:
> 1. Read current plans and watchlists (`store_get_notes(kind="plan")`).
> 2. For each watched entity, hand off to the appropriate data agent to check freshness.
> 3. If data is stale, the data agent will scrape fresh data.
> 4. After scraping, hand off to the appropriate analyst for analysis.
> 5. After analysis, hand off to the synthesizer for cross-domain patterns.
> 6. Update plans with results and next scheduled actions.
>
> Priority: user watchlist entities > high-severity events > routine coverage.

#### Plan Executor / Trader

Reads plans and predictions from storage. Executes trading actions through the risk gate.

| Capability | How |
|-----------|-----|
| Read plans | `store_get_notes(kind=plan)` |
| Read analyst/synthesizer notes | `store_get_notes(tag=prediction)` |
| Check risk budget | `store_risk_status()` |
| Execute trades | Broker tools via trading MCP (risk-gated, per-user keys) |
| Log actions | `store_save_note(kind=plan, tags=["trade_log"])` |

**System prompt**:

> You are the Plan Executor. You read trading plans and predictions from storage
> and execute them through the risk gate.
>
> Rules:
> 1. ALWAYS check `store_risk_status()` before any action.
> 2. NEVER exceed the daily action limit.
> 3. Default to dry-run mode. Only execute live if user has enabled live trading.
> 4. For each action, log via `store_save_note(kind="plan", tags=["trade_log"])`.
> 5. If risk budget is low, skip lower-confidence predictions.
> 6. Return: {actions_taken: N, actions_skipped: N, risk_remaining: N}.

**Model**: Sonnet (needs judgment for risk decisions).

**Handoff edges**: → all L1 data agents, all L2 analysts, L3 synthesizer.

---

### L5 — Live Chat Assistant (user-facing, owns plans)

The only agent the user talks to directly. Can hand off to ANY agent at any layer.
Conversational, explains reasoning, takes user input. Like L4, the chat agent
**reads and writes plans** — the user creates/modifies plans interactively,
while L4 cron executes them autonomously.

| Capability | How |
|-----------|-----|
| Answer questions | Hands off to appropriate data agent/analyst/synthesizer |
| Show data | Hands off to market-data (returns data directly) |
| Read/write plans | `store_save_note(kind=plan)`, `store_get_notes(kind=plan)` |
| Read analyst notes | `store_get_notes(kind=note)` |
| Trigger research | Hands off to research organizer |
| Execute trades | Hands off to plan executor |
| Show briefings | Reads synthesizer notes from storage |
| Explain analysis | Reads analyst notes, adds conversational explanation |

**Owns**: Same plan tools as L4 (`store_save_note`, `store_get_notes`,
`store_update_note`, `store_delete_note` for plans). Also reads notes
(analyst output) directly.

**Handoff edges**: ALL agents (market-data, osint-data, signals-data,
market-analyst, osint-analyst, signals-analyst, synthesizer, research-organizer,
plan-executor).

**System prompt**:

> You are the Trading Assistant. You are the user's primary interface.
> You can delegate to any specialist agent but you are the one who talks to the user.
>
> You own **plans** alongside the cron organizer. The user creates plans through you;
> the cron organizer executes them. You also read analyst/synthesizer notes directly.
>
> Available agents (hand off when needed):
>
> **Data agents** (L1 — use when user asks for data, fresh or stored):
> - market-data: stock prices, indicators, commodities, profiles, snapshots
> - osint-data: disasters, conflicts, weather, health, elections, transport
> - signals-data: RSS/SEC filings, Reddit, HN, crypto sentiment
>
> **Analysts** (L2 — use when user asks "what does this mean?"):
> - market-analyst: price trends, indicator analysis, sector rotation
> - osint-analyst: threat assessment, country risk, supply chain exposure
> - signals-analyst: sentiment analysis, narrative detection, filing significance
>
> **Synthesis** (L3 — use for cross-domain questions):
> - synthesizer: cross-domain patterns, composite risk scores, predictions
>
> **Operations** (L4 — use for planning and execution):
> - research-organizer: schedule research, manage watchlists
> - plan-executor: execute trading plans through risk gate
>
> Rules:
> 1. For data lookups, hand off to a data agent (it returns data directly).
> 2. For "what should I do?" questions, hand off to synthesizer then explain.
> 3. For trade execution, ALWAYS confirm with user before handing off to executor.
> 4. Keep responses conversational. Translate technical output into plain language.
> 5. Show your reasoning. Cite which agents/sources you used.

**Model**: Opus or Sonnet (needs best conversational + reasoning quality).

---

## Data Flow

```
                    L5 Live Chat ◄──── User
                    (reads/writes PLANS)
                         │
            ┌────────────┼────────────────┐
            ▼            ▼                ▼
     L4 Research    L4 Plan          L3 Synthesizer
     Organizer      Executor         (writes NOTES)
   (writes PLANS)  (writes PLANS)        │
         │              │          ┌──────┼──────┐
         ▼              ▼          ▼      ▼      ▼
    ┌────┴────┐    Risk Gate    L2 Mkt  L2 OSINT  L2 Sig
    │ Schedule │                Analyst  Analyst   Analyst
    │ data     │              (write NOTES)
    │ + analysts│                 │        │        │
    └────┬────┘                   ▼        ▼        ▼
         │                   handoff to data agents
         ▼                        │        │        │
    ┌────┴──────────────────┐     ▼        ▼        ▼
    │  L1 Data Agents       │─────────────────────────
    │  market-data          │  own: PROFILES, SNAPSHOTS, EVENTS
    │  osint-data           │  + filesystem, memory
    │  signals-data         │
    └───────┬───────────────┘
            ▼
    ┌───────────────────────────────────────────────┐
    │                   STORAGE                     │
    │  Profiles │ Snapshots │ Events │ Notes │ Plans│
    │  Files    │ Memory                            │
    └───────────────────────────────────────────────┘
```

**Key principle**: Each layer owns specific storage types:
- L1 data agents → profiles, snapshots, events (raw data)
- L2/L3 analysts → notes (analysis, assessments, predictions)
- L4/L5 chat/cron → plans (watchlists, trade plans, journals)

Storage is the shared bus. Analysts read raw data by handing off to data agents.

---

## Agent × MCP Tool Matrix

### Storage Ownership Summary

| Layer | Owns | Storage Tools |
|-------|------|---------------|
| **L1 Data Agents** | Profiles, snapshots, events | `store_snapshot`, `store_event`, `store_history`, `store_trend`, `store_get_profile`, `store_put_profile`, `store_find_profile`, `store_search_profiles`, `store_list_profiles`, `store_nearby`, `store_recent_events`, `store_archive_*`, `store_compact`, `store_aggregate`, `store_chart` |
| **L2/L3 Analysts** | Notes (analysis, assessments) | `store_save_note`, `store_get_notes`, `store_update_note`, `store_delete_note` |
| **L4/L5 Chat+Cron** | Plans (watchlists, trade plans, journals) | `store_save_note(kind=plan)`, `store_get_notes(kind=plan)`, `store_update_note`, `store_delete_note`, `store_risk_status` |

### L1 Data Agents — MCP Data Tools + Store Read/Write

| Agent | trading MCP tools | External MCPs |
|-------|------------------|---------------|
| **market-data** | `econ_indicator`, `econ_fred_*`, `econ_worldbank_*`, `econ_imf_data`, `commodity_*`, all store profile/snapshot/event tools | yahoo-finance, prediction-markets |
| **osint-data** | `disaster_*`, `conflict_*`, `weather_*`, `health_*`, `politics_*`, `transport_*`, `agri_*`, all store profile/snapshot/event tools | gdelt-cloud |
| **signals-data** | All store profile/snapshot/event tools | rss, reddit, hn, crypto-feargreed |

### L2 Analysts — Notes + Handoff to Data Agents

| Agent | trading MCP tools | Handoff edges |
|-------|------------------|---------------|
| **market-analyst** | `store_save_note`, `store_get_notes`, `store_update_note`, `store_delete_note` | → market-data |
| **osint-analyst** | Same note tools | → osint-data |
| **signals-analyst** | Same note tools | → signals-data |

### L3 Synthesizer — Notes + Handoff to All Data Agents

| Agent | trading MCP tools | Handoff edges |
|-------|------------------|---------------|
| **synthesizer** | Same note tools as L2 | → market-data, osint-data, signals-data |

### L4 Orchestrators — Plans + Handoff to All

| Agent | trading MCP tools | Handoff edges |
|-------|------------------|---------------|
| **research-organizer** | `store_save_note(kind=plan)`, `store_get_notes`, `store_update_note`, `store_delete_note`, `store_risk_status` | → all L1, all L2, L3 |
| **plan-executor** | Same plan tools + `store_risk_status` (+ future broker tools) | → all L1, all L2, L3 |

### L5 Live Chat — Plans + Notes Read + Handoff to Everything

| Agent | trading MCP tools | Handoff edges |
|-------|------------------|---------------|
| **live-chat** | `store_save_note(kind=plan)`, `store_get_notes`, `store_update_note`, `store_delete_note`, `store_risk_status` | → ALL agents (L1, L2, L3, L4) |

### Utility MCPs — Attached to Data Agents

The trading store is the primary storage layer. Filesystem is secondary
(for file exports/reports). Memory (knowledge graph) is useful for
cross-conversation entity tracking. SQLite is not needed — the trading
store's MongoDB backend covers structured queries via `store_aggregate`.

| MCP | Attached To | Purpose | Priority |
|-----|------------|---------|----------|
| filesystem | All L1 data agents | File exports, reports, documents | Secondary to trading store |
| memory | All L1 data agents | Knowledge graph across conversations | Useful for entity relations |

---

## MCP Server Configuration

### librechat.yaml

```yaml
mcpServers:

  # All MCPs hidden from general chat — agent-only access
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "__HOME__/TradeAssistant_Data/files/"]
    chatMenu: false

  memory:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-memory"]
    env:
      MEMORY_FILE_PATH: __HOME__/TradeAssistant_Data/memory.jsonl
    chatMenu: false

  # sqlite removed — trading store's MongoDB covers structured queries via store_aggregate

  trading:
    type: streamable-http
    url: http://localhost:8071/mcp
    chatMenu: false
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
        description: "Set to 'yes' for real trades. Blank = dry-run."

  # ── Tier 1 External MCPs ────────────────────

  yahoo-finance:
    command: python
    args: ["-m", "yahoo_finance_mcp"]
    chatMenu: false

  gdelt-cloud:
    type: streamable-http
    url: https://gdelt-cloud-mcp.fastmcp.app/mcp
    chatMenu: false

  prediction-markets:
    command: npx
    args: ["-y", "prediction-markets-mcp"]
    chatMenu: false

  rss:
    command: node
    args: ["__HOME__/mcps/node_modules/rss-mcp/index.js"]
    chatMenu: false

  reddit:
    command: uvx
    args: ["mcp-server-reddit"]
    chatMenu: false

endpoints:
  agents:
    recursionLimit: 25
    maxRecursionLimit: 50
    capabilities:
      - tools
      - actions
      - artifacts
      - chain
```

---

## Predefined Agents via Config (modelSpecs)

Agents are created in the Agent Builder UI (stored in MongoDB), but can be
surfaced as preset options in the UI via `modelSpecs` in `librechat.yaml`.
This makes key agents discoverable without users searching the agent list.

```yaml
modelSpecs:
  enforce: false    # false = users can still pick other agents/models
  prioritize: true  # true = these appear first in the model dropdown
  list:
    # L5 — Primary user-facing agent
    - name: "trading-assistant"
      label: "Trading Assistant"
      description: "Your AI trading assistant. Manages plans, delegates to specialist agents."
      default: true
      preset:
        endpoint: "agents"
        agent_id: "agent_LIVE_CHAT_ID"    # ← replace with actual ID from Agent Builder

    # L3 — Cross-domain synthesis
    - name: "synthesizer"
      label: "Market Synthesizer"
      description: "Cross-domain analysis: correlates disasters, markets, signals."
      preset:
        endpoint: "agents"
        agent_id: "agent_SYNTHESIZER_ID"

    # L1 — Direct data access (power users)
    - name: "market-data"
      label: "Market Data"
      description: "Direct access to market data: prices, indicators, profiles."
      preset:
        endpoint: "agents"
        agent_id: "agent_MARKET_DATA_ID"

    - name: "osint-data"
      label: "OSINT Data"
      description: "Direct access to OSINT: disasters, conflicts, weather, health."
      preset:
        endpoint: "agents"
        agent_id: "agent_OSINT_DATA_ID"
```

**Setup**: Create agents in Agent Builder UI → note their IDs → add to
`modelSpecs` in `librechat.yaml`. Agent IDs look like `agent_abc123def456`.

**Tip**: Only surface L5 (live chat) and maybe L1 data agents as modelSpecs.
L2/L3/L4 agents are used via handoff, not directly by users.

---

## Cron Schedule (L4 Research Organizer)

The research organizer runs on cron, triggering scraper → analyst → synthesizer pipelines.

| Schedule | Pipeline | Agent Chain |
|----------|----------|-------------|
| **Every 2h** | Signals refresh | signals-scraper → signals-analyst |
| **Every 6h** | OSINT refresh | osint-scraper → osint-analyst |
| **Hourly** (market hours) | Market refresh | market-scraper → market-analyst |
| **Daily 06:00** | Morning briefing | all scrapers → all analysts → synthesizer |
| **Daily 22:00** | End-of-day summary | synthesizer (reads day's data) |
| **Weekly Sun** | Deep research | research-organizer (reviews watchlists, schedules deep dives) |

**Implementation**: LibreChat Agent Chain for deterministic pipelines.
Research organizer uses handoff edges for dynamic scheduling.

---

## Handoff Reliability Mitigation

Handoff success rate is ~60%. Strategies per layer:

| Layer | Strategy |
|-------|----------|
| L1 (scrapers) | Use **Agent Chain** — deterministic, no handoff ambiguity |
| L2 (analysts) | Use **Agent Chain** after scraper completes |
| L3 (synthesizer) | Use **Agent Chain** — receives all analyst output sequentially |
| L4 (planner) | Use **Handoff Edges** — needs dynamic routing based on context |
| L5 (live chat) | Use **Handoff Edges** — interactive, unpredictable user queries |

**Rule**: Use Agent Chain for deterministic pipelines (scrape → analyze → synthesize).
Use Handoff Edges only where dynamic routing is needed (L4 planner, L5 live chat).

---

## Agent Count & Cost

| Layer | Agents | Model | Calls/Day (est.) | Purpose |
|-------|--------|-------|------------------|---------|
| L1 | 3 data agents | Haiku | ~30 | Scrape + store profiles/snapshots/events |
| L2 | 3 analysts | Sonnet | ~10 | Reason + write notes |
| L3 | 1 synthesizer | Sonnet/Opus | ~3 | Cross-domain notes |
| L4 | 2 orchestrators | Sonnet | ~5 | Plan + execute |
| L5 | 1 live chat | Opus/Sonnet | ~20 (user-driven) | Plans + conversation |
| **Total** | **10 agents** | | **~68 calls/day** | |

---

## Migration Path

### Phase 1: Data agents + chat (4 agents)

- 3 data agents (market-data, osint-data, signals-data) with MCP + store access
- 1 live chat agent with handoff edges to all 3
- Validates: MCP tool filtering, handoff reliability, storage read/write

### Phase 2: Add analysts (7 agents)

- 3 analysts (market-analyst, osint-analyst, signals-analyst) with note tools
- Each analyst has handoff edge to its data agent
- Wire as Agent Chains: data agent → analyst
- Chat gets handoff edges to analysts too

### Phase 3: Add synthesizer + cron (10 agents)

- L3 synthesizer with note tools + handoff edges to all data agents
- L4 research organizer with plan tools + handoff edges to all
- L4 plan executor with plan tools + risk gate
- Wire morning briefing chain: data agents → analysts → synthesizer

---

## Comparison to Previous Flat Architecture

| Flat (previous) | Layered (this doc) | Why |
|----------------|-------------------|-----|
| 5 agents, all peer-level | 10 agents across 5 layers | Separation of concerns: fetch vs. reason vs. synthesize |
| Main agent delegates everything | L5 chat + L4 cron both orchestrate | Autonomous ops (cron) + interactive (chat) |
| Scrapers also analyze | Data agents fetch+store; analysts reason+note | Cheaper scraping (Haiku), better analysis (Sonnet) |
| No cross-domain reasoning | L3 synthesizer sees all domains | Catches disaster→supply chain→stock correlations |
| No autonomous operations | L4 cron planner runs daily pipelines | Data stays fresh without user prompting |
| Storage is incidental | Clear ownership: data→profiles/snapshots, analysts→notes, chat/cron→plans | No ambiguity about who writes what |

---

## How LibreChat Agent Delegation Works

### Handoff Edges (v0.8.1+)

Agents are configured with **edges** to other agents in the Agent Builder UI.
When Agent A has an edge to Agent B, LibreChat auto-generates a handoff tool
that transfers control. Uses LangGraph. Transitive handoffs supported (A → B → C).

**Caveat**: ~60% reliability. Mitigate with explicit system prompts and
prefer Agent Chain for deterministic pipelines.

### Agent Chain / Mixture-of-Agents (Beta)

Chains up to 10 agents sequentially. Each receives the previous agent's output.
Better for deterministic pipelines (scrape → analyze → synthesize).

### Where Agents Live

| What | Where |
|------|-------|
| MCP server definitions | `librechat.yaml` → `mcpServers` |
| Agent definitions | Agent Builder UI → stored in **MongoDB** |
| MCP → Agent binding | Agent Builder UI → per-agent tool selection |
| Tool enable/disable | Agent Builder UI → expand MCP server → toggle individual tools |
| `chatMenu: false` | Hides MCP from general chat, agent-only access |

---

## Key Design Principles

1. **Clear ownership** — data agents own profiles/snapshots/events, analysts own notes, chat/cron own plans. No ambiguity about who writes what.

2. **Data agents are dumb** — L1 agents scrape, store, and read. No reasoning = Haiku = cheap. Run them often. They also serve as the read layer for analysts.

3. **Analysts are stateless** — L2 agents hand off to data agents for reads, reason, write notes back. They don't remember previous runs. State lives in storage.

4. **Synthesizer sees everything** — L3 is the only agent that reads across all domains (via all data agents + all analyst notes). This is where cross-domain alpha lives.

5. **Two top-level orchestrators** — cron (autonomous, scheduled) and chat (interactive, user-driven). Both own plans. Neither talks to the other.

6. **Data compounds** — every data agent run adds to the time series. Every analyst run adds notes. The synthesizer gets smarter as more data accumulates. This is the moat.

7. **Return on handoff** — when a data agent is called interactively (via handoff from analyst or chat), it returns the data directly so the caller doesn't need a second read.
