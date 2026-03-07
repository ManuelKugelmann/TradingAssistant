"""Tests for signals store MongoDB-dependent tools.

Uses unittest.mock to simulate MongoDB operations so no real database is needed.
Tests cover: _ser, _has_blocked_stage, snapshot, event, history, recent_events,
nearby, trend, aggregate, archive_snapshot, archive_history, compact, chart.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

try:
    from bson import ObjectId
except ImportError:
    # Fallback: generate fake ObjectId-like strings
    import uuid
    class ObjectId:
        def __init__(self):
            self._id = uuid.uuid4().hex[:24]
        def __str__(self):
            return self._id

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "store"))
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_unused")

import server


# ── _ser (document serialisation) ─────────────────


class TestSer:
    def test_converts_objectid_to_string(self):
        oid = ObjectId()
        doc = {"_id": oid, "data": {"x": 1}}
        result = server._ser(doc)
        assert result["_id"] == str(oid)

    def test_converts_datetime_ts_to_iso(self):
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        doc = {"_id": "abc", "ts": ts, "data": {}}
        result = server._ser(doc)
        assert result["ts"] == "2025-01-15T12:00:00+00:00"

    def test_flattens_meta_into_doc(self):
        doc = {
            "_id": "abc",
            "meta": {"entity": "DEU", "kind": "countries", "type": "indicators"},
            "data": {"gdp": 4000},
        }
        result = server._ser(doc)
        assert result["entity"] == "DEU"
        assert result["kind"] == "countries"
        assert result["type"] == "indicators"
        assert "meta" not in result

    def test_meta_does_not_overwrite_existing_keys(self):
        doc = {
            "_id": "abc",
            "entity": "ORIGINAL",
            "meta": {"entity": "FROM_META"},
        }
        result = server._ser(doc)
        assert result["entity"] == "ORIGINAL"

    def test_handles_missing_id(self):
        doc = {"data": {"x": 1}}
        result = server._ser(doc)
        assert result["_id"] == ""

    def test_non_datetime_ts_unchanged(self):
        doc = {"_id": "abc", "ts": "2025-01-15T00:00:00"}
        result = server._ser(doc)
        assert result["ts"] == "2025-01-15T00:00:00"


# ── _has_blocked_stage ────────────────────────────


class TestHasBlockedStage:
    def test_detects_top_level_blocked(self):
        pipeline = [{"$match": {}}, {"$out": "target"}]
        assert server._has_blocked_stage(pipeline) is True

    def test_detects_nested_blocked(self):
        pipeline = [{"$facet": {"a": [{"$merge": {"into": "x"}}]}}]
        assert server._has_blocked_stage(pipeline) is True

    def test_allows_clean_pipeline(self):
        pipeline = [{"$match": {"x": 1}}, {"$group": {"_id": "$y"}}]
        assert server._has_blocked_stage(pipeline) is False

    def test_empty_pipeline(self):
        assert server._has_blocked_stage([]) is False

    def test_detects_all_blocked_stages(self):
        for stage in server._BLOCKED_STAGES:
            assert server._has_blocked_stage([{stage: {}}]) is True

    def test_deeply_nested(self):
        obj = {"a": {"b": {"c": [{"$unionWith": "x"}]}}}
        assert server._has_blocked_stage(obj) is True


# ── Mock MongoDB fixtures ─────────────────────────


class FakeDB:
    """Fake MongoDB database that tracks collections by name."""

    def __init__(self):
        self._collections = {}

    def _get_col(self, name):
        if name not in self._collections:
            col = MagicMock()
            col.name = name
            cursor = MagicMock()
            cursor.sort.return_value = cursor
            cursor.limit.return_value = cursor
            cursor.__iter__ = lambda self: iter([])
            col.find.return_value = cursor
            col.aggregate.return_value = []
            col.find_one.return_value = None
            col.insert_one.return_value = MagicMock(inserted_id=ObjectId())
            col.insert_many.return_value = MagicMock(inserted_ids=[ObjectId()])
            col.delete_many.return_value = MagicMock(deleted_count=0)
            col.create_index = MagicMock()
            self._collections[name] = col
        return self._collections[name]

    def __getitem__(self, name):
        return self._get_col(name)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._get_col(name)

    def list_collection_names(self):
        return []

    def create_collection(self, name, **kwargs):
        return self._get_col(name)


@pytest.fixture
def mock_db(monkeypatch):
    """Mock _db() to return a fake database with collection tracking."""
    db = FakeDB()

    monkeypatch.setattr(server, "_client", MagicMock())
    monkeypatch.setattr(server, "_cols_ready", set())
    monkeypatch.setattr(server, "_db", lambda: db)

    return db, db._collections


# ── snapshot tool ─────────────────────────────────


class TestSnapshot:
    def test_stores_basic_snapshot(self, mock_db):
        db, cols = mock_db
        result = server.snapshot(
            kind="countries", entity="DEU", type="indicators",
            data={"gdp": 4000}, region="europe"
        )
        assert result["status"] == "ok"
        assert result["collection"] == "snap_countries"

    def test_rejects_invalid_kind(self, mock_db):
        result = server.snapshot(
            kind="invalid", entity="X", type="test", data={}
        )
        assert "error" in result

    def test_includes_geolocation(self, mock_db):
        db, cols = mock_db
        result = server.snapshot(
            kind="countries", entity="DEU", type="indicators",
            data={"gdp": 4000}, lon=13.4, lat=52.5
        )
        assert result["status"] == "ok"
        # Verify the doc passed to insert_one had location
        call_args = cols["snap_countries"].insert_one.call_args
        doc = call_args[0][0]
        assert doc["location"]["type"] == "Point"
        assert doc["location"]["coordinates"] == [13.4, 52.5]

    def test_parses_custom_ts(self, mock_db):
        db, cols = mock_db
        result = server.snapshot(
            kind="stocks", entity="AAPL", type="price",
            data={"close": 150}, ts="2025-06-15T12:00:00+00:00"
        )
        assert result["status"] == "ok"
        call_args = cols["snap_stocks"].insert_one.call_args
        doc = call_args[0][0]
        assert doc["ts"].year == 2025
        assert doc["ts"].month == 6

    def test_no_location_when_coords_missing(self, mock_db):
        db, cols = mock_db
        server.snapshot(
            kind="countries", entity="DEU", type="indicators", data={}
        )
        call_args = cols["snap_countries"].insert_one.call_args
        doc = call_args[0][0]
        assert "location" not in doc


# ── event tool ────────────────────────────────────


class TestEvent:
    def test_logs_basic_event(self, mock_db):
        result = server.event(
            subtype="earthquake", summary="Big quake",
            data={"magnitude": 7.5}, severity="high"
        )
        assert result["status"] == "ok"

    def test_event_includes_countries_and_entities(self, mock_db):
        db, cols = mock_db
        server.event(
            subtype="conflict", summary="Border clash",
            data={}, countries=["IND", "PAK"],
            entities=["BSE", "KSE"]
        )
        call_args = cols["events"].insert_one.call_args
        doc = call_args[0][0]
        assert doc["meta"]["countries"] == ["IND", "PAK"]
        assert doc["meta"]["entities"] == ["BSE", "KSE"]

    def test_event_with_geo(self, mock_db):
        db, cols = mock_db
        server.event(
            subtype="storm", summary="Hurricane",
            data={}, lon=-80.0, lat=25.0
        )
        call_args = cols["events"].insert_one.call_args
        doc = call_args[0][0]
        assert doc["location"]["coordinates"] == [-80.0, 25.0]

    def test_event_defaults_empty_lists(self, mock_db):
        db, cols = mock_db
        server.event(subtype="test", summary="Test", data={})
        call_args = cols["events"].insert_one.call_args
        doc = call_args[0][0]
        assert doc["meta"]["countries"] == []
        assert doc["meta"]["entities"] == []


# ── history tool ──────────────────────────────────


class TestHistory:
    def test_rejects_invalid_kind(self, mock_db):
        result = server.history(kind="bogus", entity="X")
        assert result[0]["error"] == "unknown kind: bogus"

    def test_builds_query_with_type(self, mock_db):
        db, cols = mock_db
        server.history(kind="stocks", entity="AAPL", type="price")
        call_args = cols["snap_stocks"].find.call_args
        q = call_args[0][0]
        assert q["meta.entity"] == "AAPL"
        assert q["meta.type"] == "price"

    def test_builds_time_range_query(self, mock_db):
        db, cols = mock_db
        server.history(
            kind="countries", entity="DEU",
            after="2025-01-01", before="2025-06-01"
        )
        call_args = cols["snap_countries"].find.call_args
        q = call_args[0][0]
        assert "$gte" in q["ts"]
        assert "$lt" in q["ts"]

    def test_applies_limit(self, mock_db):
        db, cols = mock_db
        # Pre-create collection via db access
        col = db._get_col("snap_stocks")
        cursor = col.find.return_value
        server.history(kind="stocks", entity="AAPL", limit=10)
        cursor.sort.return_value.limit.assert_called_with(10)

    def test_filters_by_region(self, mock_db):
        db, cols = mock_db
        server.history(kind="stocks", entity="AAPL", region="north_america")
        call_args = cols["snap_stocks"].find.call_args
        q = call_args[0][0]
        assert q["meta.region"] == "north_america"


# ── recent_events tool ───────────────────────────


class TestRecentEvents:
    def test_builds_base_query_with_days(self, mock_db):
        db, cols = mock_db
        server.recent_events(days=7)
        call_args = cols["events"].find.call_args
        q = call_args[0][0]
        assert "$gte" in q["ts"]

    def test_filters_by_subtype(self, mock_db):
        db, cols = mock_db
        server.recent_events(subtype="earthquake")
        q = cols["events"].find.call_args[0][0]
        assert q["meta.subtype"] == "earthquake"

    def test_filters_by_severity(self, mock_db):
        db, cols = mock_db
        server.recent_events(severity="high")
        q = cols["events"].find.call_args[0][0]
        assert q["meta.severity"] == "high"

    def test_filters_by_countries(self, mock_db):
        db, cols = mock_db
        server.recent_events(countries=["DEU", "FRA"])
        q = cols["events"].find.call_args[0][0]
        assert q["meta.countries"] == {"$in": ["DEU", "FRA"]}


# ── nearby tool ───────────────────────────────────


class TestNearby:
    def test_rejects_invalid_kind(self, mock_db):
        result = server.nearby(kind="bogus", lon=0, lat=0)
        assert result[0]["error"] == "unknown kind: bogus"

    def test_builds_geo_query(self, mock_db):
        db, cols = mock_db
        server.nearby(kind="countries", lon=13.4, lat=52.5, max_km=100)
        q = cols["snap_countries"].find.call_args[0][0]
        assert "$nearSphere" in q["location"]
        geo = q["location"]["$nearSphere"]
        assert geo["$geometry"]["coordinates"] == [13.4, 52.5]
        assert geo["$maxDistance"] == 100_000

    def test_events_uses_events_collection(self, mock_db):
        db, cols = mock_db
        server.nearby(kind="events", lon=0, lat=0)
        cols["events"].find.assert_called_once()

    def test_type_filter(self, mock_db):
        db, cols = mock_db
        server.nearby(kind="stocks", lon=0, lat=0, type="price")
        q = cols["snap_stocks"].find.call_args[0][0]
        assert q["meta.type"] == "price"


# ── trend tool ────────────────────────────────────


class TestTrend:
    def test_rejects_invalid_kind(self, mock_db):
        result = server.trend(kind="bogus", entity="X", type="y", field="z")
        assert result[0]["error"] == "unknown kind: bogus"

    def test_builds_aggregation_pipeline(self, mock_db):
        db, cols = mock_db
        server.trend(kind="countries", entity="DEU", type="indicators",
                     field="gdp", periods=6)
        pipeline = cols["snap_countries"].aggregate.call_args[0][0]
        # Check match stage
        assert pipeline[0]["$match"]["meta.entity"] == "DEU"
        assert pipeline[0]["$match"]["meta.type"] == "indicators"
        # Check limit
        assert pipeline[2]["$limit"] == 6
        # Check project extracts the right field
        assert pipeline[3]["$project"]["value"] == "$data.gdp"


# ── aggregate tool ────────────────────────────────


class TestAggregate:
    def test_blocks_dangerous_pipeline(self, mock_db):
        result = server.aggregate(
            kind="countries", pipeline=[{"$out": "hack"}]
        )
        assert result[0]["error"].startswith("pipeline contains a blocked stage")

    def test_runs_clean_pipeline(self, mock_db):
        db, cols = mock_db
        server.aggregate(
            kind="countries", pipeline=[{"$match": {"meta.entity": "DEU"}}]
        )
        cols["snap_countries"].aggregate.assert_called_once()

    def test_uses_archive_when_flagged(self, mock_db):
        db, cols = mock_db
        server.aggregate(
            kind="countries",
            pipeline=[{"$match": {}}],
            archive=True
        )
        cols["arch_countries"].aggregate.assert_called_once()

    def test_events_kind(self, mock_db):
        db, cols = mock_db
        server.aggregate(kind="events", pipeline=[{"$match": {}}])
        cols["events"].aggregate.assert_called_once()

    def test_rejects_invalid_kind(self, mock_db):
        result = server.aggregate(kind="bogus", pipeline=[])
        assert result[0]["error"] == "unknown kind: bogus"


# ── archive_snapshot tool ─────────────────────────


class TestArchiveSnapshot:
    def test_stores_in_archive_collection(self, mock_db):
        db, cols = mock_db
        result = server.archive_snapshot(
            kind="countries", entity="DEU", type="indicators",
            data={"gdp": 4000}, region="europe"
        )
        assert result["status"] == "ok"
        assert result["collection"] == "arch_countries"

    def test_rejects_invalid_kind(self, mock_db):
        result = server.archive_snapshot(
            kind="bogus", entity="X", type="test", data={}
        )
        assert "error" in result

    def test_parses_custom_ts(self, mock_db):
        db, cols = mock_db
        server.archive_snapshot(
            kind="stocks", entity="AAPL", type="price",
            data={"close": 150}, ts="2020-01-01T00:00:00"
        )
        doc = cols["arch_stocks"].insert_one.call_args[0][0]
        assert doc["ts"].year == 2020


# ── archive_history tool ──────────────────────────


class TestArchiveHistory:
    def test_rejects_invalid_kind(self, mock_db):
        result = server.archive_history(kind="bogus", entity="X")
        assert result[0]["error"] == "unknown kind: bogus"

    def test_builds_query_with_filters(self, mock_db):
        db, cols = mock_db
        server.archive_history(
            kind="countries", entity="DEU", type="indicators",
            region="europe", after="2020-01-01", before="2025-01-01"
        )
        q = cols["arch_countries"].find.call_args[0][0]
        assert q["meta.entity"] == "DEU"
        assert q["meta.type"] == "indicators"
        assert q["meta.region"] == "europe"
        assert "$gte" in q["ts"]
        assert "$lt" in q["ts"]


# ── compact tool ──────────────────────────────────


class TestCompact:
    def test_rejects_invalid_kind(self, mock_db):
        result = server.compact(kind="bogus", entity="X", type="test")
        assert "error" in result

    def test_rejects_invalid_bucket(self, mock_db):
        result = server.compact(
            kind="countries", entity="DEU", type="indicators",
            bucket="yearly"
        )
        assert "error" in result
        assert "invalid bucket" in result["error"]

    def test_nothing_to_compact(self, mock_db):
        db, cols = mock_db
        db._get_col("snap_countries").find_one.return_value = None
        result = server.compact(
            kind="countries", entity="DEU", type="indicators"
        )
        assert result["status"] == "nothing_to_compact"

    def test_compact_success(self, mock_db):
        db, cols = mock_db
        snap_col = db._get_col("snap_countries")
        arch_col = db._get_col("arch_countries")

        snap_col.find_one.return_value = {
            "data": {"gdp": 4000.0, "name": "Germany"},
            "meta": {"source": "wb", "region": "europe"},
        }

        bucket_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        snap_col.aggregate.return_value = [
            {
                "_id": bucket_ts,
                "gdp": 4100.5,
                "name": "Germany",
                "_source": "wb",
                "_region": "europe",
                "_count": 3,
            }
        ]

        arch_col.insert_many.return_value = MagicMock(
            inserted_ids=[ObjectId()]
        )
        snap_col.delete_many.return_value = MagicMock(deleted_count=3)

        result = server.compact(
            kind="countries", entity="DEU", type="indicators",
            older_than_days=90, bucket="month"
        )
        assert result["status"] == "ok"
        assert result["buckets_created"] == 1
        assert result["snapshots_deleted"] == 3

    def test_compact_partial_insert_returns_error(self, mock_db):
        db, cols = mock_db
        snap_col = db._get_col("snap_countries")
        arch_col = db._get_col("arch_countries")

        snap_col.find_one.return_value = {
            "data": {"gdp": 4000.0},
            "meta": {"source": "wb", "region": "europe"},
        }
        bucket_ts1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        bucket_ts2 = datetime(2024, 2, 1, tzinfo=timezone.utc)
        snap_col.aggregate.return_value = [
            {"_id": bucket_ts1, "gdp": 4000.0, "_source": "wb", "_region": "europe", "_count": 2},
            {"_id": bucket_ts2, "gdp": 4100.0, "_source": "wb", "_region": "europe", "_count": 2},
        ]
        arch_col.insert_many.return_value = MagicMock(
            inserted_ids=[ObjectId()]
        )

        result = server.compact(
            kind="countries", entity="DEU", type="indicators"
        )
        assert "error" in result
        assert "partial" in result["error"]


# ── chart tool ────────────────────────────────────


class TestChart:
    def test_rejects_invalid_kind(self, mock_db):
        result = server.chart(
            kind="bogus", entity="X", type="test", fields=["a"]
        )
        assert "Unknown kind" in result

    def test_no_data_returns_message(self, mock_db):
        db, cols = mock_db
        db._get_col("snap_countries").aggregate.return_value = []
        result = server.chart(
            kind="countries", entity="DEU", type="indicators",
            fields=["gdp"]
        )
        assert "No data found" in result

    def test_generates_html(self, mock_db):
        db, cols = mock_db
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        db._get_col("snap_stocks").aggregate.return_value = [
            {"ts": ts, "value": 150.0},
            {"ts": ts + timedelta(days=30), "value": 155.0},
        ]
        result = server.chart(
            kind="stocks", entity="AAPL", type="price",
            fields=["close"], title="AAPL Price"
        )
        assert "<!DOCTYPE html>" in result
        assert "Plotly.newPlot" in result
        assert "AAPL Price" in result

    def test_uses_archive_when_flagged(self, mock_db):
        db, cols = mock_db
        db._get_col("arch_countries").aggregate.return_value = []
        server.chart(
            kind="countries", entity="DEU", type="indicators",
            fields=["gdp"], archive=True
        )
        cols["arch_countries"].aggregate.assert_called()

    def test_chart_type_bar(self, mock_db):
        db, cols = mock_db
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        db._get_col("snap_stocks").aggregate.return_value = [
            {"ts": ts, "value": 100},
        ]
        result = server.chart(
            kind="stocks", entity="AAPL", type="price",
            fields=["close"], chart_type="bar"
        )
        assert '"type": "bar"' in result

    def test_chart_type_scatter(self, mock_db):
        db, cols = mock_db
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        db._get_col("snap_stocks").aggregate.return_value = [
            {"ts": ts, "value": 100},
        ]
        result = server.chart(
            kind="stocks", entity="AAPL", type="price",
            fields=["close"], chart_type="scatter"
        )
        assert "markers" in result
