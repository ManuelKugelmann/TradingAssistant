"""MCP Signals Store — Hybrid profile/snapshot store.

Profiles: JSON files on disk (git-tracked, human-editable).
Two MongoDB Atlas timeseries collections (auto-created on first access):
  snapshots — recent signals, 1-year TTL, hours granularity
  archive   — long-term history, no TTL, days granularity

Timeseries layout (both collections):
  timeField  = "ts"      (always full datetime, even in archive)
  metaField  = "meta"    (entity, type, source, + event-specific fields)
  data       = measurement payload
"""
from fastmcp import FastMCP
from pymongo import MongoClient
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import os

from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("signals-store", description="Hybrid profile/snapshot store")

PROFILES = Path(os.environ.get("PROFILES_DIR", "./profiles"))
_client = None
_cols_ready = set()

KIND_PATHS = {
    "countries": "countries",
    "stocks": "entities/stocks",
    "etfs": "entities/etfs",
    "crypto": "entities/crypto",
    "indices": "entities/indices",
    "sources": "sources",
}

SNAPSHOTS_TTL = 365 * 86400         # 1 year


def _db():
    global _client
    if not _client:
        uri = os.environ.get("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGO_URI not set")
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


def _col():
    """Return the snapshots timeseries collection (1-year TTL)."""
    _ensure_ts("snapshots", ttl=SNAPSHOTS_TTL)
    return _db().snapshots


def _archive_col():
    """Return the archive timeseries collection (no TTL, days granularity)."""
    _ensure_ts("archive", granularity="days")
    return _db().archive


def _profile_dir(kind: str) -> Path | None:
    sub = KIND_PATHS.get(kind)
    return PROFILES / sub if sub else None


# ── File profiles ──────────────────────────────────


@mcp.tool()
def get_profile(kind: str, id: str) -> dict:
    """Read a profile. kind: countries, stocks, etfs, crypto, indices, sources."""
    d = _profile_dir(kind)
    if not d:
        return {"error": f"unknown kind: {kind}"}
    p = d / f"{id}.json"
    if not p.exists():
        return {"error": f"not found: {kind}/{id}"}
    return json.loads(p.read_text())


@mcp.tool()
def put_profile(kind: str, id: str, data: dict) -> dict:
    """Create or merge a profile. Shallow-merges with existing."""
    d = _profile_dir(kind)
    if not d:
        return {"error": f"unknown kind: {kind}"}
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{id}.json"
    existing = json.loads(p.read_text()) if p.exists() else {}
    existing.update(data)
    existing["_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    return {"path": str(p), "status": "ok"}


@mcp.tool()
def list_profiles(kind: str) -> list[str]:
    """List all profile IDs for a kind."""
    d = _profile_dir(kind)
    if not d or not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json") if not p.stem.startswith("_"))


@mcp.tool()
def search_profiles(kind: str, field: str, value: str) -> list[dict]:
    """Search profiles by dot-path field (e.g. 'exposure.countries', 'tags', 'sector').
    Checks if value is in list/string or equals field."""
    results = []
    for pid in list_profiles(kind):
        prof = get_profile(kind, pid)
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


# ── Atlas snapshots ────────────────────────────────


@mcp.tool()
def snapshot(entity: str, type: str, data: dict,
             source: str = "", ts: str = "") -> dict:
    """Store a timestamped snapshot. entity: profile ID (e.g. 'DEU', 'AAPL').
    type: indicators, price, fundamentals.
    TTL is managed at the collection level (365 days from ts)."""
    now = datetime.now(timezone.utc)
    doc = {
        "ts": datetime.fromisoformat(ts) if ts else now,
        "meta": {"entity": entity, "type": type, "source": source},
        "data": data,
    }
    r = _col().insert_one(doc)
    return {"id": str(r.inserted_id), "status": "ok"}


@mcp.tool()
def event(subtype: str, summary: str, data: dict,
          severity: str = "medium", countries: list[str] = [],
          entities: list[str] = [], source: str = "",
          ts: str = "") -> dict:
    """Log a signal event. severity: low, medium, high, critical.
    TTL is managed at the collection level (365 days from ts)."""
    now = datetime.now(timezone.utc)
    doc = {
        "ts": datetime.fromisoformat(ts) if ts else now,
        "meta": {
            "type": "event",
            "subtype": subtype,
            "severity": severity,
            "countries": countries,
            "entities": entities,
            "source": source,
        },
        "summary": summary,
        "data": data,
    }
    r = _col().insert_one(doc)
    return {"id": str(r.inserted_id), "status": "ok"}


@mcp.tool()
def history(entity: str, type: str = "",
            after: str = "", before: str = "",
            limit: int = 100) -> list[dict]:
    """Get snapshot history for an entity. Newest first.
    Fields are under meta.entity, meta.type, meta.source."""
    q: dict = {"meta.entity": entity}
    if type:
        q["meta.type"] = type
    if after or before:
        q["ts"] = {}
        if after:
            q["ts"]["$gte"] = datetime.fromisoformat(after)
        if before:
            q["ts"]["$lt"] = datetime.fromisoformat(before)
    rows = _col().find(q).sort("ts", -1).limit(limit)
    return [_ser(r) for r in rows]


@mcp.tool()
def recent_events(subtype: str = "", severity: str = "",
                  countries: list[str] = [], days: int = 30,
                  limit: int = 50) -> list[dict]:
    """Query recent events. Filters on meta.type='event' and meta sub-fields."""
    q: dict = {
        "meta.type": "event",
        "ts": {"$gte": datetime.now(timezone.utc) - timedelta(days=days)},
    }
    if subtype:
        q["meta.subtype"] = subtype
    if severity:
        q["meta.severity"] = severity
    if countries:
        q["meta.countries"] = {"$in": countries}
    rows = _col().find(q).sort("ts", -1).limit(limit)
    return [_ser(r) for r in rows]


@mcp.tool()
def trend(entity: str, type: str, field: str,
          periods: int = 12) -> list[dict]:
    """Extract a single field's trend over time.
    field: key in data, e.g. 'gdp_growth_pct' or 'close'."""
    pipeline = [
        {"$match": {"meta.entity": entity, "meta.type": type}},
        {"$sort": {"ts": -1}},
        {"$limit": periods},
        {"$project": {"ts": 1, "value": f"$data.{field}", "_id": 0}},
        {"$sort": {"ts": 1}},
    ]
    return list(_col().aggregate(pipeline))


@mcp.tool()
def aggregate(pipeline: list[dict], collection: str = "snapshots") -> list[dict]:
    """Run a raw MongoDB aggregation pipeline.
    collection: 'snapshots' (default) or 'archive'.
    Note: filter fields are under 'meta' (meta.entity, meta.type, meta.source, etc.).
    Example: [{"$match": {"meta.type": "event", "meta.subtype": "earthquake"}},
              {"$group": {"_id": "$data.country", "count": {"$sum": 1}}}]"""
    col = _archive_col() if collection == "archive" else _col()
    return [_ser(r) for r in col.aggregate(pipeline)]


# ── Archive (long-term history) ───────────────────


@mcp.tool()
def archive_snapshot(entity: str, type: str, data: dict,
                     source: str = "", ts: str = "") -> dict:
    """Store a long-term snapshot in the archive (no TTL, kept forever).
    Use for historical macro data, yearly GDP, quarterly earnings, etc."""
    now = datetime.now(timezone.utc)
    doc = {
        "ts": datetime.fromisoformat(ts) if ts else now,
        "meta": {"entity": entity, "type": type, "source": source},
        "data": data,
    }
    r = _archive_col().insert_one(doc)
    return {"id": str(r.inserted_id), "status": "ok"}


@mcp.tool()
def archive_history(entity: str, type: str = "",
                    after: str = "", before: str = "",
                    limit: int = 200) -> list[dict]:
    """Query the long-term archive. Same interface as history()."""
    q: dict = {"meta.entity": entity}
    if type:
        q["meta.type"] = type
    if after or before:
        q["ts"] = {}
        if after:
            q["ts"]["$gte"] = datetime.fromisoformat(after)
        if before:
            q["ts"]["$lt"] = datetime.fromisoformat(before)
    rows = _archive_col().find(q).sort("ts", -1).limit(limit)
    return [_ser(r) for r in rows]


@mcp.tool()
def compact(entity: str, type: str, older_than_days: int = 90,
            bucket: str = "month") -> dict:
    """Downsample old snapshots into the archive by averaging numeric fields.
    bucket: 'week', 'month', or 'quarter'.
    Aggregates snapshots older than older_than_days, writes monthly/weekly
    averages to archive, then deletes the originals from snapshots."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    date_trunc = {
        "week": {"$dateTrunc": {"date": "$ts", "unit": "week"}},
        "month": {"$dateTrunc": {"date": "$ts", "unit": "month"}},
        "quarter": {"$dateTrunc": {"date": "$ts", "unit": "quarter"}},
    }
    if bucket not in date_trunc:
        return {"error": f"invalid bucket: {bucket}, use week/month/quarter"}

    # Step 1: find all data keys from a sample doc
    sample = _col().find_one(
        {"meta.entity": entity, "meta.type": type, "ts": {"$lt": cutoff}}
    )
    if not sample:
        return {"status": "nothing_to_compact", "entity": entity, "type": type}

    data_keys = list(sample.get("data", {}).keys())

    # Step 2: aggregate into buckets, averaging all numeric fields
    group_accumulators = {
        k.replace(".", "_"): {"$avg": f"$data.{k}"} for k in data_keys
    }
    group_accumulators["_source"] = {"$first": "$meta.source"}
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

    buckets = list(_col().aggregate(pipeline))
    if not buckets:
        return {"status": "nothing_to_compact", "entity": entity, "type": type}

    # Step 3: insert compacted docs into archive
    archive_docs = []
    for b in buckets:
        data = {}
        for k in data_keys:
            safe_k = k.replace(".", "_")
            val = b.get(safe_k)
            if val is not None:
                data[k] = round(val, 6) if isinstance(val, float) else val
        data["_samples"] = b["_count"]
        archive_docs.append({
            "ts": b["_id"],
            "meta": {
                "entity": entity,
                "type": type,
                "source": b.get("_source", ""),
            },
            "data": data,
        })

    _archive_col().insert_many(archive_docs)

    # Step 4: delete compacted originals from snapshots
    result = _col().delete_many(
        {"meta.entity": entity, "meta.type": type, "ts": {"$lt": cutoff}}
    )

    return {
        "status": "ok",
        "buckets_created": len(archive_docs),
        "snapshots_deleted": result.deleted_count,
        "bucket_size": bucket,
        "oldest": archive_docs[0]["ts"].isoformat(),
        "newest": archive_docs[-1]["ts"].isoformat(),
    }


def _ser(doc: dict) -> dict:
    doc["_id"] = str(doc.get("_id", ""))
    for k in ("ts",):
        if isinstance(doc.get(k), datetime):
            doc[k] = doc[k].isoformat()
    # Flatten meta into top-level for caller convenience
    if "meta" in doc:
        doc.update(doc.pop("meta"))
    return doc

if __name__ == "__main__":
    mcp.run(transport="stdio")
