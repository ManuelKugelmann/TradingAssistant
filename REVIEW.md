# Code Review — TradingAssistant

Full security and quality audit of the entire codebase. Date: 2026-03-06.

---

## CRITICAL Issues

### 1. Path Traversal in Profile Tools
**File:** `src/store/server.py:57-80`

The `id` parameter is used directly in file paths without sanitization:
```python
p = d / f"{id}.json"
```
An attacker (or LLM prompt injection) could pass `id="../../.env"` to read `.env` via `get_profile` or **overwrite arbitrary files** via `put_profile`.

**Fix:** Validate `id` contains only `[A-Za-z0-9_-]` and that the resolved path stays within the profiles directory.

### 2. Raw MongoDB Aggregation Pipeline Exposed
**File:** `src/store/server.py:216-221`

```python
def aggregate(pipeline: list[dict]) -> list[dict]:
    return [_ser(r) for r in _col().aggregate(pipeline)]
```
Accepts arbitrary pipelines. A prompt injection could use `$out`/`$merge` to overwrite collections, or `$lookup` to read other collections.

**Fix:** Block dangerous stages (`$out`, `$merge`, `$unionWith`, `$collStats`, `$currentOp`) or remove this tool entirely.

### 3. Mutable Default Arguments
**File:** `src/store/server.py:142,185`

```python
def event(..., countries: list[str] = [], entities: list[str] = []):
def recent_events(..., countries: list[str] = []):
```
Classic Python bug: mutable defaults are shared across all calls.

**Fix:** Use `None` defaults with `countries = countries or []` inside.

### 4. Shell Injection in `trap`
**Files:** `TradeAssistant.sh:146`, `bootstrap.sh:35`

```bash
trap "rm -rf $TMP" EXIT
```
Double-quoted trap expands `$TMP` at definition time but without quotes. If path contains special chars, `rm -rf` could hit unintended targets.

**Fix:** `trap 'rm -rf "$TMP"' EXIT`

### 5. Operator Precedence Bug in Git Update
**File:** `TradeAssistant.sh:75-77`

```bash
git -C "$STACK" pull --ff-only origin "$BRANCH" 2>/dev/null || \
    git -C "$STACK" fetch origin "$BRANCH" && \
    git -C "$STACK" reset --hard "origin/$BRANCH"
```
Due to `||`/`&&` precedence, if `pull --ff-only` **succeeds**, `reset --hard` still runs. Needs braces:
```bash
... || { git ... fetch ... && git ... reset --hard ...; }
```

### 6. OData Injection in WHO API
**File:** `health_server.py:18`

```python
filters.append(f"SpatialDim eq '{country}'")
```
User-supplied `country` is interpolated directly into OData filter. Attacker can break out with `' or 1 eq 1 or '`.

---

## WARNING Issues

### 7. Environment Variable Name Mismatches
`.env.example` names don't match the code:

| `.env.example` | Code reads | File |
|---|---|---|
| `GOOGLE_CIVIC_API_KEY` | `GOOGLE_API_KEY` | `elections_server.py:9` |
| `AIS_STREAM_API_KEY` | `AISSTREAM_API_KEY` | `transport_server.py:9` |
| `CLOUDFLARE_API_TOKEN` | `CF_API_TOKEN` | `infra_server.py:9` |

Users following `.env.example` will have non-functional API keys.

### 8. `datetime.utcnow()` Deprecated
**File:** `disasters_server.py:13`

Deprecated since Python 3.12. Use `datetime.now(timezone.utc)` (already used in `server.py`).

### 9. No Timeout on Most HTTP Clients
Many servers create `httpx.AsyncClient()` without timeout:
- `agri_server.py:16,42,56`
- `conflict_server.py:16,37,49,58`
- `commodities_server.py:37`
- `elections_server.py:20,31`
- `health_server.py:32,43,57`
- `humanitarian_server.py:17,26,40`
- `macro_server.py:19,32,47,58,71`
- `infra_server.py:20,35`

Default httpx timeout is 5s, but external APIs can hang longer or need more time.

### 10. No Error Handling on Domain Servers
All 12 servers use bare `r.raise_for_status()` with no try/except. API outages return raw tracebacks instead of clean error dicts.

### 11. CI References Non-Existent `install.sh`
**File:** `.github/workflows/release.yml:54`

```yaml
files: |
  librechat-bundle.tar.gz
  install.sh
```
No `install.sh` exists. Dead config (softprops/action-gh-release skips missing files silently).

### 12. `nightly-git-commit.sh` Never Pushes
Commits profile changes locally but never pushes. Commits accumulate forever on the server.

### 13. Comtrade API Key Sent When Empty
**File:** `commodities_server.py:23`

Unlike other servers that check `if not KEY: return {"error": ...}`, this sends an empty key, causing auth errors rather than a clean message.

### 14. `type` Shadows Python Built-in
**File:** `src/store/server.py:121,165,202`

`type` is used as a parameter name, shadowing the built-in.

### 15. Index Creation at Module Load
**File:** `src/store/server.py:232-235`

Runs `_ensure_indexes()` at import time. If MONGO_URI isn't configured, it silently fails and indexes are never created later.

### 16. Sequential HTTP in `space_weather()`
**File:** `weather_server.py:49-52`

Three independent requests made sequentially. Could use `asyncio.gather()` to cut latency by 3x.

### 17. `search_profiles` Reads Every File
**File:** `src/store/server.py:96-114`

O(n) disk reads per query with no caching. Will degrade with hundreds of profiles.

### 18. Domain Server `.env` Not Loaded via LibreChat
**File:** `librechat-uberspace/config/librechat.yaml`

Domain servers call `load_dotenv()` which searches CWD. When launched by LibreChat (not supervisord), CWD is LibreChat's dir, not the stack dir. API keys won't be found.

Only `signals-store` gets an explicit env var (`PROFILES_DIR`). Domain servers need their API keys passed via `env:` blocks in the yaml.

### 19. `deploy.conf` Variable Not Used by Ops Script
`deploy.conf` defines `GH_REPO_STACK` but `TradeAssistant.sh:16` reads `GH_REPO` (set before config is sourced). The config variable is effectively dead.

---

## STYLE Issues

### 20. `_schema.json` Files Aren't JSON Schema
The schema files use plain-text descriptions instead of actual JSON Schema. `put_profile` accepts any data shape with no validation.

### 21. `librechat.yaml` Uses `npx -y` Despite Bundled Packages
CI bundles `node_modules`, but yaml still uses `npx -y` which re-downloads on each startup.

### 22. Inconsistent ID Casing in Profiles
Countries: `DEU`, `USA` (uppercase). Sources: `faostat`, `open-meteo` (lowercase). Inconsistent convention.

### 23. CI Removes `package-lock.json`
**File:** `.github/workflows/release.yml:43`

Prevents reproducible builds. Each install fetches latest minor versions.

---

## Priority Fix Order

1. **Path traversal** in `get_profile`/`put_profile` (security)
2. **Restrict `aggregate` tool** (security)
3. **Fix `.env.example` variable names** (users blocked)
4. **Fix operator precedence** in `TradeAssistant.sh:75-77` (data loss risk)
5. **Pass env vars** to domain servers in `librechat.yaml` (functionality)
6. **Fix mutable defaults** in `server.py` (correctness)
7. **Add error handling** to domain servers (reliability)
8. **Add timeouts** consistently (reliability)
