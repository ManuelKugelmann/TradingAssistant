"""MCP Signals Store — Hybrid profile/snapshot store.

Profiles: JSON files on disk at profiles/{region}/{kind}/{id}.json
MongoDB: Per-kind timeseries collections with geo support:
  snap_{kind}  — recent data, 1-year TTL, hours granularity
  arch_{kind}  — long-term archive, no TTL, days granularity
  events       — cross-kind signal events, 1-year TTL

All docs share: ts (datetime), meta (entity, kind, region, type, source),
data (payload), location (optional GeoJSON Point).
"""
from fastmcp import FastMCP
from pymongo import MongoClient
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import os
import re

from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("signals-store", instructions="Hybrid profile/snapshot store")

PROFILES = Path(os.environ.get("PROFILES_DIR", "./profiles"))
_client = None
_cols_ready = set()

VALID_KINDS = frozenset({
    "countries", "stocks", "etfs", "crypto", "indices", "sources",
    "commodities", "crops", "materials", "products", "companies",
})

_RESERVED_DIRS = frozenset({"SCHEMAS"})

SNAPSHOTS_TTL = 365 * 86400         # 1 year

_SAFE_ID = re.compile(r'^[A-Za-z0-9_-]+$')


# ── MongoDB helpers ───────────────────────────────


def _db():
    global _client
    if not _client:
        uri = os.environ.get("MONGO_URI_SIGNALS") or os.environ.get("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGO_URI_SIGNALS (or MONGO_URI) not set")
        _client = MongoClient(uri)
    return _client.signals


def _ensure_ts(name: str, ttl: int | None = None, granularity: str = "hours"):
    """Auto-create a timeseries collection if it doesn't exist."""
    global _cols_ready
    if name in _cols_ready:
        return
    db = _db()
    if name not in db.list_collection_names():
        opts: dict = {
            "timeseries": {
                "timeField": "ts",
                "metaField": "meta",
                "granularity": granularity,
            },
        }
        if ttl is not None:
            opts["expireAfterSeconds"] = ttl
        db.create_collection(name, **opts)
    _cols_ready.add(name)


def _snap_col(kind: str):
    """Return the snapshots collection for a kind (1-year TTL)."""
    name = f"snap_{kind}"
    _ensure_ts(name, ttl=SNAPSHOTS_TTL)
    col = _db()[name]
    if f"{name}_geo" not in _cols_ready:
        col.create_index([("location", "2dsphere")],
                         sparse=True, background=True)
        _cols_ready.add(f"{name}_geo")
    return col


def _arch_col(kind: str):
    """Return the archive collection for a kind (no TTL)."""
    name = f"arch_{kind}"
    _ensure_ts(name, granularity="days")
    return _db()[name]


def _events_col():
    """Return the cross-kind events collection."""
    _ensure_ts("events", ttl=SNAPSHOTS_TTL)
    col = _db().events
    if "events_geo" not in _cols_ready:
        col.create_index([("location", "2dsphere")],
                         sparse=True, background=True)
        _cols_ready.add("events_geo")
    return col


def _ser(doc: dict) -> dict:
    doc["_id"] = str(doc.get("_id", ""))
    for k in ("ts",):
        if isinstance(doc.get(k), datetime):
            doc[k] = doc[k].isoformat()
    if "meta" in doc:
        meta = doc.pop("meta")
        for k, v in meta.items():
            if k not in doc:
                doc[k] = v
    return doc


# ── Profile filesystem helpers ────────────────────


def _regions() -> list[str]:
    """Discover geographic region folders under PROFILES/."""
    if not PROFILES.exists():
        return []
    return sorted([
        d.name for d in PROFILES.iterdir()
        if d.is_dir() and d.name not in _RESERVED_DIRS
        and not d.name.startswith(".")
    ])


def _find_profile_path(kind: str, id: str) -> Path | None:
    """Scan all region folders to find an existing profile file."""
    for region in _regions():
        p = PROFILES / region / kind / f"{id}.json"
        if p.exists():
            return p
    return None


def _safe_profile_path(region: str, kind: str, id: str) -> tuple[Path, dict | None]:
    """Validate region+kind+id and return (path, None) or (_, error_dict)."""
    if not _SAFE_ID.match(id):
        return Path(), {"error": f"invalid id: {id} (only A-Z, a-z, 0-9, _, -)"}
    if not _SAFE_ID.match(region):
        return Path(), {"error": f"invalid region: {region}"}
    if kind not in VALID_KINDS:
        return Path(), {"error": f"unknown kind: {kind}, valid: {sorted(VALID_KINDS)}"}
    p = (PROFILES / region / kind / f"{id}.json").resolve()
    if not str(p).startswith(str(PROFILES.resolve())):
        return Path(), {"error": f"path traversal blocked: {id}"}
    return p, None


# ── Index helpers ─────────────────────────────────


def _kind_index_path(kind: str) -> Path:
    """Return path to the kind's top-level index file."""
    return PROFILES / f"INDEX_{kind}.json"


def _index_entry(kind: str, id: str, data: dict, region: str = "") -> dict:
    """Build a single index entry from profile data."""
    entry: dict = {"id": id, "kind": kind, "name": data.get("name", id),
                   "region": region}
    for key in ("tags", "sector"):
        if key in data:
            entry[key] = data[key]
    return entry


def _update_index(kind: str, id: str, data: dict, region: str = ""):
    """Incrementally update a single entry in INDEX_{kind}.json."""
    idx_path = _kind_index_path(kind)
    index = json.loads(idx_path.read_text()) if idx_path.exists() else []
    index = [e for e in index if e["id"] != id]
    index.append(_index_entry(kind, id, data, region))
    index.sort(key=lambda e: e["id"])
    idx_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))


def _rebuild_kind_index(kind: str) -> list[dict]:
    """Rebuild INDEX_{kind}.json by scanning all region folders."""
    index = []
    for region in _regions():
        d = PROFILES / region / kind
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            if f.stem.startswith("_"):
                continue
            try:
                data = json.loads(f.read_text())
                index.append(_index_entry(kind, f.stem, data, region))
            except Exception:
                pass
    index.sort(key=lambda e: e["id"])
    idx_path = _kind_index_path(kind)
    idx_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    return index


def _rebuild_all_indexes() -> int:
    """Rebuild INDEX_{kind}.json for every kind. Returns total entry count."""
    total = 0
    for kind in VALID_KINDS:
        total += len(_rebuild_kind_index(kind))
    return total


def _load_all_indexes() -> list[dict]:
    """Load and merge all per-kind INDEX files for cross-kind search."""
    merged = []
    for kind in VALID_KINDS:
        idx_path = _kind_index_path(kind)
        if idx_path.exists():
            try:
                merged.extend(json.loads(idx_path.read_text()))
            except Exception:
                pass
    return merged


# ── Schema + lint helpers ─────────────────────────


def _load_schema(kind: str) -> dict | None:
    """Load the schema for a kind from SCHEMAS/{kind}.schema.json."""
    p = PROFILES / "SCHEMAS" / f"{kind}.schema.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _lint_one(kind: str, id: str, data: dict, schema: dict | None) -> list[str]:
    """Lint a single profile. Returns list of issue strings."""
    issues = []
    if not schema:
        return issues
    required = schema.get("required", [])
    props = schema.get("properties", {})
    for field in required:
        if field not in data:
            issues.append(f"missing required field: {field}")
    for field, desc in props.items():
        if field not in data:
            continue
        val = data[field]
        if isinstance(desc, dict) and not isinstance(val, dict):
            issues.append(f"{field}: expected object, got {type(val).__name__}")
        if isinstance(desc, str) and "array" in desc.lower() and not isinstance(val, list):
            issues.append(f"{field}: expected array, got {type(val).__name__}")
    return issues


# ── Profile tools ─────────────────────────────────
# Layout: profiles/{region}/{kind}/{id}.json
# API: kind + id identify a profile. region optional for reads, required for writes.
# Mongo snapshot tools mirror the same (kind, id, region) parameters + time fields.


@mcp.tool()
def get_profile(kind: str, id: str, region: str = "") -> dict:
    """Read a profile. If region omitted, searches all regions.
    kind: countries, stocks, etfs, crypto, indices, sources,
    commodities, crops, materials, products, companies."""
    if not _SAFE_ID.match(id):
        return {"error": f"invalid id: {id}"}
    if kind not in VALID_KINDS:
        return {"error": f"unknown kind: {kind}"}
    if region:
        p, err = _safe_profile_path(region, kind, id)
        if err:
            return err
    else:
        p = _find_profile_path(kind, id)
    if not p or not p.exists():
        return {"error": f"not found: {kind}/{id}"}
    return json.loads(p.read_text())


@mcp.tool()
def put_profile(kind: str, id: str, data: dict,
                region: str = "global") -> dict:
    """Create or merge a profile. Shallow-merges with existing.
    region: geographic folder (e.g. europe, north_america, global).
    Defaults to 'global'. If profile already exists in another region,
    updates it there instead."""
    if not _SAFE_ID.match(id):
        return {"error": f"invalid id: {id}"}
    if kind not in VALID_KINDS:
        return {"error": f"unknown kind: {kind}"}
    existing_path = _find_profile_path(kind, id)
    if existing_path:
        p = existing_path
    else:
        p, err = _safe_profile_path(region, kind, id)
        if err:
            return err
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(p.read_text()) if p.exists() else {}
    existing.update(data)
    existing["_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    actual_region = p.parent.parent.name
    _update_index(kind, id, existing, actual_region)
    return {"path": str(p), "region": actual_region, "status": "ok"}


@mcp.tool()
def list_profiles(kind: str, region: str = "") -> list[dict]:
    """List all profiles for a kind. Optionally filter by region.
    Returns [{id, name, region}, ...]."""
    if kind not in VALID_KINDS:
        return []
    regions_to_scan = [region] if region else _regions()
    result = []
    for r in regions_to_scan:
        d = PROFILES / r / kind
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            if f.stem.startswith("_"):
                continue
            try:
                data = json.loads(f.read_text())
                result.append({"id": f.stem, "name": data.get("name", f.stem),
                               "region": r})
            except Exception:
                result.append({"id": f.stem, "name": f.stem, "region": r})
    return result


@mcp.tool()
def find_profile(query: str, region: str = "") -> list[dict]:
    """Find profiles by name, ID, or tag across all kinds and regions.
    Case-insensitive partial match. Optionally filter by region.
    Returns [{id, kind, name, region}, ...]."""
    q = query.lower()
    index = _load_all_indexes()
    if not index:
        _rebuild_all_indexes()
        index = _load_all_indexes()
    matches = []
    for entry in index:
        if region and entry.get("region") != region:
            continue
        if (q in entry["id"].lower()
                or q in entry.get("name", "").lower()
                or any(q in t.lower() for t in entry.get("tags", []))):
            matches.append(entry)
    return matches


@mcp.tool()
def search_profiles(kind: str, field: str, value: str,
                    region: str = "") -> list[dict]:
    """Search profiles by dot-path field (e.g. 'exposure.countries', 'tags').
    Optionally filter by region."""
    results = []
    for entry in list_profiles(kind, region):
        prof = get_profile(kind, entry["id"])
        if "error" in prof:
            continue
        obj = prof
        for key in field.split("."):
            obj = obj.get(key) if isinstance(obj, dict) else None
            if obj is None:
                break
        if obj is None:
            continue
        if isinstance(obj, list) and value in obj:
            results.append(prof)
        elif isinstance(obj, str) and value.lower() in obj.lower():
            results.append(prof)
        elif str(obj) == value:
            results.append(prof)
    return results


@mcp.tool()
def list_regions() -> list[dict]:
    """List all geographic regions and the kinds they contain."""
    result = []
    for region in _regions():
        rd = PROFILES / region
        kinds = sorted([
            d.name for d in rd.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ])
        result.append({"region": region, "kinds": kinds})
    return result


@mcp.tool()
def rebuild_index(kind: str | None = None) -> dict:
    """Force full rebuild of INDEX_{kind}.json from profile files on disk.
    If kind given, rebuild only that kind. Otherwise rebuild all."""
    if kind:
        entries = _rebuild_kind_index(kind)
        return {"status": "ok", "kind": kind, "entries": len(entries)}
    total = _rebuild_all_indexes()
    return {"status": "ok", "kinds": sorted(VALID_KINDS), "entries": total}


@mcp.tool()
def lint_profiles(kind: str | None = None, id: str | None = None) -> dict:
    """Validate profiles against their schema. Check required fields and types.
    If kind+id given, lint one. If only kind, lint all of that kind.
    If neither, lint everything. Returns {ok: [...], issues: {id: [...]}}."""
    results: dict = {"ok": [], "issues": {}}
    targets: list[tuple[str, str]] = []
    if kind and id:
        targets.append((kind, id))
    elif kind:
        for entry in list_profiles(kind):
            targets.append((kind, entry["id"]))
    else:
        for k in VALID_KINDS:
            for entry in list_profiles(k):
                targets.append((k, entry["id"]))
    for k, pid in targets:
        schema = _load_schema(k)
        prof = get_profile(k, pid)
        if "error" in prof:
            results["issues"][f"{k}/{pid}"] = [prof["error"]]
            continue
        issues = _lint_one(k, pid, prof, schema)
        key = f"{k}/{pid}"
        if issues:
            results["issues"][key] = issues
        else:
            results["ok"].append(key)
    return results


# ── Snapshot tools ────────────────────────────────
# Mirror profile tools API: kind, id (entity), region — plus time fields.
# Each kind has its own MongoDB timeseries collection (snap_{kind} / arch_{kind}).


@mcp.tool()
def snapshot(kind: str, entity: str, type: str, data: dict,
             region: str = "", source: str = "", ts: str = "",
             lon: float | None = None, lat: float | None = None) -> dict:
    """Store a timestamped snapshot. Goes into snap_{kind} collection.
    kind: profile kind (stocks, countries, etc.).
    entity: profile ID (e.g. 'DEU', 'AAPL').
    type: data category (indicators, price, fundamentals).
    region: geographic region key (same as profile region).
    lon/lat: optional coordinates for geo queries."""
    if kind not in VALID_KINDS:
        return {"error": f"unknown kind: {kind}"}
    now = datetime.now(timezone.utc)
    doc = {
        "ts": datetime.fromisoformat(ts) if ts else now,
        "meta": {"entity": entity, "kind": kind, "region": region,
                 "type": type, "source": source},
        "data": data,
    }
    if lon is not None and lat is not None:
        doc["location"] = {"type": "Point", "coordinates": [lon, lat]}
    r = _snap_col(kind).insert_one(doc)
    return {"id": str(r.inserted_id), "collection": f"snap_{kind}", "status": "ok"}


@mcp.tool()
def event(subtype: str, summary: str, data: dict,
          severity: str = "medium", countries: list[str] | None = None,
          entities: list[str] | None = None, region: str = "",
          source: str = "", ts: str = "",
          lon: float | None = None, lat: float | None = None) -> dict:
    """Log a signal event. severity: low, medium, high, critical.
    region: geographic region key. lon/lat: optional coordinates."""
    now = datetime.now(timezone.utc)
    doc = {
        "ts": datetime.fromisoformat(ts) if ts else now,
        "meta": {
            "type": "event",
            "subtype": subtype,
            "severity": severity,
            "region": region,
            "countries": countries or [],
            "entities": entities or [],
            "source": source,
        },
        "summary": summary,
        "data": data,
    }
    if lon is not None and lat is not None:
        doc["location"] = {"type": "Point", "coordinates": [lon, lat]}
    r = _events_col().insert_one(doc)
    return {"id": str(r.inserted_id), "status": "ok"}


@mcp.tool()
def history(kind: str, entity: str, type: str = "",
            region: str = "", after: str = "", before: str = "",
            limit: int = 100) -> list[dict]:
    """Get snapshot history for an entity. Newest first.
    kind: profile kind. Optionally filter by region and time range."""
    if kind not in VALID_KINDS:
        return [{"error": f"unknown kind: {kind}"}]
    q: dict = {"meta.entity": entity}
    if type:
        q["meta.type"] = type
    if region:
        q["meta.region"] = region
    if after or before:
        q["ts"] = {}
        if after:
            q["ts"]["$gte"] = datetime.fromisoformat(after)
        if before:
            q["ts"]["$lt"] = datetime.fromisoformat(before)
    rows = _snap_col(kind).find(q).sort("ts", -1).limit(limit)
    return [_ser(r) for r in rows]


@mcp.tool()
def recent_events(subtype: str = "", severity: str = "",
                  region: str = "", countries: list[str] | None = None,
                  days: int = 30, limit: int = 50) -> list[dict]:
    """Query recent events. Optionally filter by region."""
    q: dict = {
        "ts": {"$gte": datetime.now(timezone.utc) - timedelta(days=days)},
    }
    if subtype:
        q["meta.subtype"] = subtype
    if severity:
        q["meta.severity"] = severity
    if region:
        q["meta.region"] = region
    if countries:
        q["meta.countries"] = {"$in": countries}
    rows = _events_col().find(q).sort("ts", -1).limit(limit)
    return [_ser(r) for r in rows]


@mcp.tool()
def nearby(kind: str, lon: float, lat: float,
           max_km: float = 500, type: str = "",
           limit: int = 50) -> list[dict]:
    """Find snapshots or events near a geographic point.
    kind: profile kind or 'events'. max_km: search radius."""
    q: dict = {
        "location": {
            "$nearSphere": {
                "$geometry": {"type": "Point", "coordinates": [lon, lat]},
                "$maxDistance": max_km * 1000,
            }
        }
    }
    if type:
        q["meta.type"] = type
    if kind == "events":
        col = _events_col()
    elif kind in VALID_KINDS:
        col = _snap_col(kind)
    else:
        return [{"error": f"unknown kind: {kind}"}]
    return [_ser(r) for r in col.find(q).limit(limit)]


@mcp.tool()
def trend(kind: str, entity: str, type: str, field: str,
          periods: int = 12) -> list[dict]:
    """Extract a single field's trend over time.
    field: key in data, e.g. 'gdp_growth_pct' or 'close'."""
    if kind not in VALID_KINDS:
        return [{"error": f"unknown kind: {kind}"}]
    pipeline = [
        {"$match": {"meta.entity": entity, "meta.type": type}},
        {"$sort": {"ts": -1}},
        {"$limit": periods},
        {"$project": {"ts": 1, "value": f"$data.{field}", "_id": 0}},
        {"$sort": {"ts": 1}},
    ]
    return list(_snap_col(kind).aggregate(pipeline))


_BLOCKED_STAGES = frozenset({
    "$out", "$merge", "$unionWith", "$collStats", "$currentOp",
    "$listSessions", "$planCacheStats",
})


def _has_blocked_stage(obj) -> bool:
    """Recursively check for blocked aggregation stages in nested pipelines."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in _BLOCKED_STAGES:
                return True
            if _has_blocked_stage(val):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if _has_blocked_stage(item):
                return True
    return False


@mcp.tool()
def aggregate(kind: str, pipeline: list[dict],
              archive: bool = False) -> list[dict]:
    """Run a read-only MongoDB aggregation pipeline on a kind's collection.
    kind: profile kind or 'events'. archive: query arch_{kind} instead."""
    if _has_blocked_stage(pipeline):
        return [{"error": "pipeline contains a blocked stage ($out, $merge, etc.)"}]
    if kind == "events":
        col = _events_col()
    elif kind in VALID_KINDS:
        col = _arch_col(kind) if archive else _snap_col(kind)
    else:
        return [{"error": f"unknown kind: {kind}"}]
    return [_ser(r) for r in col.aggregate(pipeline)]


# ── Charts ────────────────────────────────────────

_CHART_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>body{{margin:0;font-family:system-ui}}#c{{width:100%;height:100vh}}</style>
</head><body><div id="c"></div><script>
Plotly.newPlot('c',{traces},{layout},{{responsive:true}});
</script></body></html>"""


@mcp.tool()
def chart(kind: str, entity: str, type: str, fields: list[str],
          periods: int = 24, archive: bool = False,
          chart_type: str = "line", title: str = "") -> str:
    """Generate an interactive Plotly HTML chart from timeseries data.
    kind: profile kind. entity: e.g. 'DEU'. type: e.g. 'indicators'.
    fields: data keys to plot. chart_type: 'line', 'bar', 'scatter'."""
    if kind not in VALID_KINDS:
        return f"Unknown kind: {kind}"
    col = _arch_col(kind) if archive else _snap_col(kind)

    traces = []
    for field in fields:
        pipeline = [
            {"$match": {"meta.entity": entity, "meta.type": type}},
            {"$sort": {"ts": -1}},
            {"$limit": periods},
            {"$project": {"ts": 1, "value": f"$data.{field}", "_id": 0}},
            {"$sort": {"ts": 1}},
        ]
        points = list(col.aggregate(pipeline))
        if not points:
            continue
        x = [p["ts"].isoformat() if isinstance(p["ts"], datetime) else p["ts"]
             for p in points]
        y = [p.get("value") for p in points]
        mode = ("lines+markers" if chart_type == "line"
                else "markers" if chart_type == "scatter" else "")
        trace: dict = {"x": x, "y": y, "name": field}
        if chart_type in ("line", "scatter"):
            trace["type"] = "scatter"
            trace["mode"] = mode
        else:
            trace["type"] = "bar"
        traces.append(trace)

    if not traces:
        return f"No data found for {kind}/{entity}/{type} fields={fields}"

    chart_title = title or f"{entity} — {type}"
    layout = json.dumps({
        "title": chart_title,
        "xaxis": {"title": "Date"},
        "template": "plotly_white",
        "margin": {"t": 40, "r": 20, "b": 40, "l": 60},
    })
    return _CHART_HTML.format(traces=json.dumps(traces), layout=layout)


# ── Archive ───────────────────────────────────────


@mcp.tool()
def archive_snapshot(kind: str, entity: str, type: str, data: dict,
                     region: str = "", source: str = "", ts: str = "") -> dict:
    """Store a long-term snapshot in arch_{kind} (no TTL).
    For historical macro data, yearly GDP, quarterly earnings, etc."""
    if kind not in VALID_KINDS:
        return {"error": f"unknown kind: {kind}"}
    now = datetime.now(timezone.utc)
    doc = {
        "ts": datetime.fromisoformat(ts) if ts else now,
        "meta": {"entity": entity, "kind": kind, "region": region,
                 "type": type, "source": source},
        "data": data,
    }
    r = _arch_col(kind).insert_one(doc)
    return {"id": str(r.inserted_id), "collection": f"arch_{kind}", "status": "ok"}


@mcp.tool()
def archive_history(kind: str, entity: str, type: str = "",
                    region: str = "", after: str = "", before: str = "",
                    limit: int = 200) -> list[dict]:
    """Query the kind's long-term archive. Optionally filter by region."""
    if kind not in VALID_KINDS:
        return [{"error": f"unknown kind: {kind}"}]
    q: dict = {"meta.entity": entity}
    if type:
        q["meta.type"] = type
    if region:
        q["meta.region"] = region
    if after or before:
        q["ts"] = {}
        if after:
            q["ts"]["$gte"] = datetime.fromisoformat(after)
        if before:
            q["ts"]["$lt"] = datetime.fromisoformat(before)
    rows = _arch_col(kind).find(q).sort("ts", -1).limit(limit)
    return [_ser(r) for r in rows]


@mcp.tool()
def compact(kind: str, entity: str, type: str, older_than_days: int = 90,
            bucket: str = "month") -> dict:
    """Downsample old snapshots into arch_{kind} by averaging numerics.
    bucket: 'week', 'month', or 'quarter'."""
    if kind not in VALID_KINDS:
        return {"error": f"unknown kind: {kind}"}
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    date_trunc = {
        "week": {"$dateTrunc": {"date": "$ts", "unit": "week"}},
        "month": {"$dateTrunc": {"date": "$ts", "unit": "month"}},
        "quarter": {"$dateTrunc": {"date": "$ts", "unit": "quarter"}},
    }
    if bucket not in date_trunc:
        return {"error": f"invalid bucket: {bucket}, use week/month/quarter"}

    snap = _snap_col(kind)
    sample = snap.find_one(
        {"meta.entity": entity, "meta.type": type, "ts": {"$lt": cutoff}}
    )
    if not sample:
        return {"status": "nothing_to_compact", "entity": entity, "type": type}

    sample_data = sample.get("data", {})
    data_keys = list(sample_data.keys())

    group_accumulators = {}
    for k in data_keys:
        safe_k = k.replace(".", "_")
        val = sample_data[k]
        if isinstance(val, (int, float)):
            group_accumulators[safe_k] = {"$avg": f"$data.{k}"}
        else:
            group_accumulators[safe_k] = {"$first": f"$data.{k}"}
    group_accumulators["_source"] = {"$first": "$meta.source"}
    group_accumulators["_region"] = {"$first": "$meta.region"}
    group_accumulators["_count"] = {"$sum": 1}

    pipeline = [
        {"$match": {
            "meta.entity": entity, "meta.type": type, "ts": {"$lt": cutoff},
        }},
        {"$group": {
            "_id": date_trunc[bucket],
            **group_accumulators,
        }},
        {"$sort": {"_id": 1}},
    ]

    buckets_result = list(snap.aggregate(pipeline))
    if not buckets_result:
        return {"status": "nothing_to_compact", "entity": entity, "type": type}

    archive_docs = []
    for b in buckets_result:
        d = {}
        for k in data_keys:
            safe_k = k.replace(".", "_")
            val = b.get(safe_k)
            if val is not None:
                d[k] = round(val, 6) if isinstance(val, float) else val
        d["_samples"] = b["_count"]
        archive_docs.append({
            "ts": b["_id"],
            "meta": {
                "entity": entity,
                "kind": kind,
                "region": b.get("_region", ""),
                "type": type,
                "source": b.get("_source", ""),
            },
            "data": d,
        })

    arch_result = _arch_col(kind).insert_many(archive_docs)
    if len(arch_result.inserted_ids) != len(archive_docs):
        return {"error": "partial archive insert — snapshots preserved",
                "archived": len(arch_result.inserted_ids),
                "expected": len(archive_docs)}

    result = snap.delete_many(
        {"meta.entity": entity, "meta.type": type, "ts": {"$lt": cutoff}}
    )

    return {
        "status": "ok",
        "collection": f"snap_{kind}",
        "buckets_created": len(archive_docs),
        "snapshots_deleted": result.deleted_count,
        "bucket_size": bucket,
        "oldest": archive_docs[0]["ts"].isoformat(),
        "newest": archive_docs[-1]["ts"].isoformat(),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
