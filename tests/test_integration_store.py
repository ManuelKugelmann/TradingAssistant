"""Integration tests for the signals store against a real MongoDB instance.

Requires MONGO_URI or MONGO_URI_SIGNALS pointing to a live database.
Uses a dedicated 'test_signals' database and cleans up after itself.
Marked with pytest.mark.integration to exclude from normal CI.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

MONGO_URI = os.environ.get("MONGO_URI_SIGNALS") or os.environ.get("MONGO_URI")

skip_no_mongo = pytest.mark.skipif(not MONGO_URI, reason="MONGO_URI not set")


@skip_no_mongo
class TestStoreLive:
    """Test signals store profile + snapshot tools against real MongoDB."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        # Point store at temp profiles dir and real MongoDB
        os.environ["PROFILES_DIR"] = str(tmp_path / "profiles")
        os.environ.setdefault("MONGO_URI", MONGO_URI)

        # Create a minimal profile structure
        p = tmp_path / "profiles" / "europe" / "countries"
        p.mkdir(parents=True)
        (p / "DEU.json").write_text(
            '{"id":"DEU","name":"Germany","kind":"countries",'
            '"region":"europe","tags":["eu","g7"]}'
        )

        # Force-reimport the store module fresh
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "store"))

        # Reset cached client so it reconnects
        import server
        server._client = None
        server._cols_ready = set()
        server.PROFILES = Path(os.environ["PROFILES_DIR"])
        self.s = server

        yield

        # Cleanup: drop test collections
        try:
            db = server._db()
            for name in db.list_collection_names():
                if name.startswith("snap_") or name.startswith("arch_") or name == "events":
                    db.drop_collection(name)
        except Exception:
            pass
        server._client = None
        server._cols_ready = set()

    # ── Profile tools ────────────────────────────────

    def test_get_profile(self):
        result = run(self.s.get_profile(kind="countries", id="DEU"))
        assert result["id"] == "DEU"
        assert result["name"] == "Germany"

    def test_put_and_get_profile(self):
        run(self.s.put_profile(
            kind="countries", id="FRA", region="europe",
            data={"name": "France", "tags": ["eu", "g7"]}))
        result = run(self.s.get_profile(kind="countries", id="FRA"))
        assert result["name"] == "France"

    def test_list_profiles(self):
        result = run(self.s.list_profiles(kind="countries", region="europe"))
        assert any(p["id"] == "DEU" for p in result)

    def test_find_profile(self):
        result = run(self.s.find_profile(query="Germany"))
        assert any(p["id"] == "DEU" for p in result)

    # ── Snapshot tools ───────────────────────────────

    def test_snapshot_and_history(self):
        result = run(self.s.snapshot(
            kind="countries", entity="DEU", type="gdp",
            data={"value": 4.2, "unit": "trillion_usd"},
            region="europe"))
        assert "inserted" in result or "id" in str(result).lower()

        hist = run(self.s.history(kind="countries", entity="DEU", type="gdp"))
        assert isinstance(hist, list)
        assert len(hist) >= 1

    def test_trend(self):
        # Insert a few snapshots first
        for val in [4.0, 4.1, 4.2]:
            run(self.s.snapshot(
                kind="countries", entity="DEU", type="gdp_trend_test",
                data={"value": val}, region="europe"))
        result = run(self.s.trend(
            kind="countries", entity="DEU",
            type="gdp_trend_test", field="value", periods=3))
        assert isinstance(result, (dict, list))

    def test_event_and_recent(self):
        result = run(self.s.event(
            subtype="test_event", summary="Integration test event",
            data={"detail": "testing"}, region="europe"))
        assert "inserted" in result or "id" in str(result).lower()

        events = run(self.s.recent_events(subtype="test_event"))
        assert isinstance(events, list)
        assert len(events) >= 1

    def test_archive_snapshot_and_history(self):
        result = run(self.s.archive_snapshot(
            kind="countries", entity="DEU", type="annual_gdp",
            data={"value": 4.0, "year": 2023}, region="europe"))
        assert "inserted" in result or "id" in str(result).lower()

        hist = run(self.s.archive_history(
            kind="countries", entity="DEU", type="annual_gdp"))
        assert isinstance(hist, list)

    def test_aggregate(self):
        # Insert a snapshot to have data
        run(self.s.snapshot(
            kind="countries", entity="DEU", type="agg_test",
            data={"value": 1}, region="europe"))
        result = run(self.s.aggregate(
            kind="countries",
            pipeline=[{"$limit": 5}]))
        assert isinstance(result, list)

    # ── Nearby (geo) ─────────────────────────────────

    def test_nearby(self):
        # Insert snapshot with location
        run(self.s.snapshot(
            kind="countries", entity="DEU", type="geo_test",
            data={"value": 1}, region="europe",
            lon=11.58, lat=48.14))
        result = run(self.s.nearby(
            kind="countries", lon=11.58, lat=48.14, max_km=100))
        assert isinstance(result, list)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)
