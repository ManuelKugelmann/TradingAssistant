"""Tests for signals store profile, index, and lint logic.

These tests exercise the pure-Python filesystem code in src/store/server.py
without needing MongoDB. MongoDB-dependent snapshot tools are not tested here.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src/ to path so we can import the store module's internals
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "store"))

# Prevent module-level MongoClient from connecting
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_unused")


@pytest.fixture(autouse=True)
def profiles_dir(tmp_path, monkeypatch):
    """Set up a temporary profiles directory for each test."""
    import server

    monkeypatch.setattr(server, "PROFILES", tmp_path)

    # Create basic region/kind structure
    for region in ("europe", "north_america", "global"):
        for kind in ("countries", "stocks", "sources"):
            (tmp_path / region / kind).mkdir(parents=True)

    # Add SCHEMAS dir with a countries schema
    schemas = tmp_path / "SCHEMAS"
    schemas.mkdir()
    schema = {
        "$schema": "Profile schema for countries",
        "required": ["id", "name"],
        "properties": {
            "id": "ISO3 country code",
            "name": "Full country name",
            "tags": "Array of group memberships",
        },
    }
    (schemas / "countries.schema.json").write_text(json.dumps(schema))

    yield tmp_path


@pytest.fixture
def store():
    import server
    return server


# ── Region discovery ──────────────────────────────


class TestRegions:
    def test_discovers_region_dirs(self, store, profiles_dir):
        regions = store._regions()
        assert "europe" in regions
        assert "north_america" in regions
        assert "global" in regions

    def test_excludes_schemas_dir(self, store, profiles_dir):
        regions = store._regions()
        assert "SCHEMAS" not in regions

    def test_excludes_dotfiles(self, store, profiles_dir):
        (profiles_dir / ".hidden").mkdir()
        regions = store._regions()
        assert ".hidden" not in regions


# ── Profile path safety ──────────────────────────


class TestSafeProfilePath:
    def test_valid_path(self, store):
        p, err = store._safe_profile_path("europe", "countries", "DEU")
        assert err is None
        assert p.name == "DEU.json"

    def test_invalid_id_rejected(self, store):
        _, err = store._safe_profile_path("europe", "countries", "../etc/passwd")
        assert err is not None
        assert "invalid id" in err["error"]

    def test_invalid_region_rejected(self, store):
        _, err = store._safe_profile_path("../../etc", "countries", "DEU")
        assert err is not None
        assert "invalid region" in err["error"]

    def test_unknown_kind_rejected(self, store):
        _, err = store._safe_profile_path("europe", "weapons", "AK47")
        assert err is not None
        assert "unknown kind" in err["error"]


# ── get_profile ──────────────────────────────────


class TestGetProfile:
    def test_reads_existing_profile(self, store, profiles_dir):
        data = {"id": "DEU", "name": "Germany"}
        (profiles_dir / "europe" / "countries" / "DEU.json").write_text(
            json.dumps(data)
        )
        result = store.get_profile("countries", "DEU")
        assert result["name"] == "Germany"

    def test_finds_across_regions(self, store, profiles_dir):
        data = {"id": "USA", "name": "United States"}
        (profiles_dir / "north_america" / "countries" / "USA.json").write_text(
            json.dumps(data)
        )
        result = store.get_profile("countries", "USA")
        assert result["name"] == "United States"

    def test_not_found_returns_error(self, store):
        result = store.get_profile("countries", "ZZZ")
        assert "error" in result

    def test_invalid_kind_returns_error(self, store):
        result = store.get_profile("invalid_kind", "FOO")
        assert "error" in result

    def test_invalid_id_returns_error(self, store):
        result = store.get_profile("countries", "../hack")
        assert "error" in result


# ── put_profile ──────────────────────────────────


class TestPutProfile:
    def test_creates_new_profile(self, store, profiles_dir):
        result = store.put_profile("countries", "FRA",
                                   {"id": "FRA", "name": "France"},
                                   region="europe")
        assert result["status"] == "ok"
        assert result["region"] == "europe"
        p = profiles_dir / "europe" / "countries" / "FRA.json"
        assert p.exists()
        data = json.loads(p.read_text())
        assert data["name"] == "France"
        assert "_updated" in data

    def test_merges_with_existing(self, store, profiles_dir):
        (profiles_dir / "europe" / "countries" / "DEU.json").write_text(
            json.dumps({"id": "DEU", "name": "Germany", "currency": "EUR"})
        )
        result = store.put_profile("countries", "DEU",
                                   {"population": 83_000_000})
        assert result["status"] == "ok"
        data = json.loads(
            (profiles_dir / "europe" / "countries" / "DEU.json").read_text()
        )
        assert data["currency"] == "EUR"
        assert data["population"] == 83_000_000

    def test_updates_in_existing_region(self, store, profiles_dir):
        """If profile exists in europe, put_profile with region=global still updates in europe."""
        (profiles_dir / "europe" / "countries" / "DEU.json").write_text(
            json.dumps({"id": "DEU", "name": "Germany"})
        )
        result = store.put_profile("countries", "DEU",
                                   {"capital": "Berlin"}, region="global")
        assert result["region"] == "europe"

    def test_defaults_to_global_region(self, store, profiles_dir):
        result = store.put_profile("sources", "test_src",
                                   {"id": "test_src", "name": "Test Source"})
        assert result["region"] == "global"

    def test_creates_index_entry(self, store, profiles_dir):
        store.put_profile("countries", "JPN",
                          {"id": "JPN", "name": "Japan"},
                          region="global")
        idx_path = profiles_dir / "INDEX_countries.json"
        assert idx_path.exists()
        index = json.loads(idx_path.read_text())
        ids = [e["id"] for e in index]
        assert "JPN" in ids

    def test_rejects_invalid_id(self, store):
        result = store.put_profile("countries", "../bad", {"name": "bad"})
        assert "error" in result


# ── list_profiles ────────────────────────────────


class TestListProfiles:
    def test_lists_all_regions(self, store, profiles_dir):
        (profiles_dir / "europe" / "countries" / "DEU.json").write_text(
            json.dumps({"id": "DEU", "name": "Germany"})
        )
        (profiles_dir / "north_america" / "countries" / "USA.json").write_text(
            json.dumps({"id": "USA", "name": "United States"})
        )
        result = store.list_profiles("countries")
        ids = [e["id"] for e in result]
        assert "DEU" in ids
        assert "USA" in ids

    def test_filters_by_region(self, store, profiles_dir):
        (profiles_dir / "europe" / "countries" / "DEU.json").write_text(
            json.dumps({"id": "DEU", "name": "Germany"})
        )
        (profiles_dir / "north_america" / "countries" / "USA.json").write_text(
            json.dumps({"id": "USA", "name": "United States"})
        )
        result = store.list_profiles("countries", region="europe")
        ids = [e["id"] for e in result]
        assert "DEU" in ids
        assert "USA" not in ids

    def test_skips_underscore_files(self, store, profiles_dir):
        (profiles_dir / "europe" / "countries" / "_schema.json").write_text("{}")
        result = store.list_profiles("countries")
        ids = [e["id"] for e in result]
        assert "_schema" not in ids

    def test_unknown_kind_returns_empty(self, store):
        result = store.list_profiles("nonexistent")
        assert result == []


# ── find_profile (index-based search) ────────────


class TestFindProfile:
    def test_finds_by_name(self, store, profiles_dir):
        store.put_profile("countries", "DEU",
                          {"id": "DEU", "name": "Germany"},
                          region="europe")
        result = store.find_profile("germ")
        assert any(e["id"] == "DEU" for e in result)

    def test_finds_by_id(self, store, profiles_dir):
        store.put_profile("countries", "DEU",
                          {"id": "DEU", "name": "Germany"},
                          region="europe")
        result = store.find_profile("DEU")
        assert any(e["id"] == "DEU" for e in result)

    def test_finds_by_tag(self, store, profiles_dir):
        store.put_profile("countries", "DEU",
                          {"id": "DEU", "name": "Germany", "tags": ["EU", "G7"]},
                          region="europe")
        result = store.find_profile("EU")
        assert any(e["id"] == "DEU" for e in result)

    def test_filters_by_region(self, store, profiles_dir):
        store.put_profile("countries", "DEU",
                          {"id": "DEU", "name": "Germany"},
                          region="europe")
        result = store.find_profile("DEU", region="north_america")
        assert not any(e["id"] == "DEU" for e in result)


# ── rebuild_index ────────────────────────────────


class TestRebuildIndex:
    def test_rebuilds_single_kind(self, store, profiles_dir):
        (profiles_dir / "europe" / "countries" / "DEU.json").write_text(
            json.dumps({"id": "DEU", "name": "Germany"})
        )
        (profiles_dir / "north_america" / "countries" / "USA.json").write_text(
            json.dumps({"id": "USA", "name": "United States"})
        )
        result = store.rebuild_index("countries")
        assert result["status"] == "ok"
        assert result["entries"] == 2

        idx = json.loads(
            (profiles_dir / "INDEX_countries.json").read_text()
        )
        ids = [e["id"] for e in idx]
        assert "DEU" in ids
        assert "USA" in ids

    def test_rebuilds_all_kinds(self, store, profiles_dir):
        (profiles_dir / "europe" / "countries" / "DEU.json").write_text(
            json.dumps({"id": "DEU", "name": "Germany"})
        )
        (profiles_dir / "global" / "sources" / "test.json").write_text(
            json.dumps({"id": "test", "name": "Test Source"})
        )
        result = store.rebuild_index()
        assert result["status"] == "ok"
        assert result["entries"] >= 2


# ── list_regions ─────────────────────────────────


class TestListRegions:
    def test_returns_regions_with_kinds(self, store, profiles_dir):
        result = store.list_regions()
        region_names = [r["region"] for r in result]
        assert "europe" in region_names
        europe = next(r for r in result if r["region"] == "europe")
        assert "countries" in europe["kinds"]


# ── lint_profiles ────────────────────────────────


class TestLintProfiles:
    def test_valid_profile_passes(self, store, profiles_dir):
        store.put_profile("countries", "DEU",
                          {"id": "DEU", "name": "Germany"},
                          region="europe")
        result = store.lint_profiles("countries", "DEU")
        assert "countries/DEU" in result["ok"]
        assert "countries/DEU" not in result["issues"]

    def test_missing_required_field_flagged(self, store, profiles_dir):
        # Write a countries profile without "name" (required by schema)
        (profiles_dir / "europe" / "countries" / "BAD.json").write_text(
            json.dumps({"id": "BAD"})
        )
        result = store.lint_profiles("countries", "BAD")
        assert "countries/BAD" in result["issues"]
        issues = result["issues"]["countries/BAD"]
        assert any("name" in i for i in issues)

    def test_lint_all_of_kind(self, store, profiles_dir):
        store.put_profile("countries", "DEU",
                          {"id": "DEU", "name": "Germany"},
                          region="europe")
        (profiles_dir / "europe" / "countries" / "BAD.json").write_text(
            json.dumps({"id": "BAD"})
        )
        result = store.lint_profiles("countries")
        assert "countries/DEU" in result["ok"]
        assert "countries/BAD" in result["issues"]

    def test_no_schema_means_no_issues(self, store, profiles_dir):
        store.put_profile("stocks", "AAPL",
                          {"id": "AAPL", "name": "Apple"},
                          region="north_america")
        result = store.lint_profiles("stocks", "AAPL")
        assert "stocks/AAPL" in result["ok"]


# ── _lint_one internals ──────────────────────────


class TestLintOne:
    def test_type_mismatch_detected(self, store):
        schema = {
            "required": [],
            "properties": {
                "trade": {"top_exports": "exports"},
            },
        }
        issues = store._lint_one("countries", "X",
                                 {"trade": "not_a_dict"}, schema)
        assert any("trade" in i for i in issues)

    def test_array_type_mismatch(self, store):
        schema = {
            "required": [],
            "properties": {
                "tags": "Array of values",
            },
        }
        issues = store._lint_one("countries", "X",
                                 {"tags": "not_an_array"}, schema)
        assert any("tags" in i for i in issues)


# ── search_profiles ──────────────────────────────


class TestSearchProfiles:
    def test_search_by_string_field(self, store, profiles_dir):
        store.put_profile("countries", "DEU",
                          {"id": "DEU", "name": "Germany", "currency": "EUR"},
                          region="europe")
        result = store.search_profiles("countries", "currency", "EUR")
        assert any(p["id"] == "DEU" for p in result)

    def test_search_by_list_membership(self, store, profiles_dir):
        store.put_profile("countries", "DEU",
                          {"id": "DEU", "name": "Germany",
                           "tags": ["EU", "G7", "NATO"]},
                          region="europe")
        result = store.search_profiles("countries", "tags", "EU")
        assert any(p["id"] == "DEU" for p in result)

    def test_search_no_match(self, store, profiles_dir):
        store.put_profile("countries", "DEU",
                          {"id": "DEU", "name": "Germany", "currency": "EUR"},
                          region="europe")
        result = store.search_profiles("countries", "currency", "USD")
        assert not any(p.get("id") == "DEU" for p in result)


# ── Index helpers ────────────────────────────────


class TestIndexHelpers:
    def test_index_entry_structure(self, store):
        entry = store._index_entry("countries", "DEU",
                                   {"name": "Germany", "tags": ["EU"]},
                                   "europe")
        assert entry["id"] == "DEU"
        assert entry["kind"] == "countries"
        assert entry["name"] == "Germany"
        assert entry["region"] == "europe"
        assert entry["tags"] == ["EU"]

    def test_incremental_update_replaces(self, store, profiles_dir):
        store._update_index("countries", "DEU",
                            {"name": "Germany"}, "europe")
        store._update_index("countries", "DEU",
                            {"name": "Deutschland"}, "europe")
        idx = json.loads(
            (profiles_dir / "INDEX_countries.json").read_text()
        )
        deu_entries = [e for e in idx if e["id"] == "DEU"]
        assert len(deu_entries) == 1
        assert deu_entries[0]["name"] == "Deutschland"


# ── VALID_KINDS ──────────────────────────────────


class TestValidKinds:
    def test_all_expected_kinds_present(self, store):
        expected = {"countries", "stocks", "etfs", "crypto", "indices",
                    "sources", "commodities", "crops", "materials",
                    "products", "companies"}
        assert store.VALID_KINDS == expected

    def test_blocked_agg_stages(self, store):
        for stage in ("$out", "$merge", "$unionWith"):
            assert stage in store._BLOCKED_STAGES


# ── Snapshot tools (mocked MongoDB) ─────────────


class TestSnapshotTools:
    """Tests for MongoDB-dependent snapshot tools using mocked pymongo."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        import server as store
        self.store = store
        store._client = None
        store._cols_ready = set()
        yield
        store._client = None
        store._cols_ready = set()

    def test_snapshot_rejects_invalid_kind(self):
        result = self.store.snapshot("badkind", "X", "price", {"close": 100})
        assert "error" in result

    def test_snapshot_inserts_doc(self, mock_mongo):
        client, db = mock_mongo
        mock_col = MagicMock()
        mock_col.insert_one.return_value = MagicMock(inserted_id="abc123")
        db.__getitem__ = MagicMock(return_value=mock_col)
        self.store._client = client
        self.store._cols_ready = {"snap_stocks", "snap_stocks_geo"}

        result = self.store.snapshot("stocks", "AAPL", "price",
                                     {"close": 150.0, "volume": 1_000_000})
        assert result["status"] == "ok"
        assert result["collection"] == "snap_stocks"
        mock_col.insert_one.assert_called_once()
        doc = mock_col.insert_one.call_args[0][0]
        assert doc["meta"]["entity"] == "AAPL"
        assert doc["data"]["close"] == 150.0

    def test_snapshot_with_geo(self, mock_mongo):
        client, db = mock_mongo
        mock_col = MagicMock()
        mock_col.insert_one.return_value = MagicMock(inserted_id="geo123")
        db.__getitem__ = MagicMock(return_value=mock_col)
        self.store._client = client
        self.store._cols_ready = {"snap_countries", "snap_countries_geo"}

        result = self.store.snapshot("countries", "DEU", "indicators",
                                     {"gdp": 4.0}, lon=10.45, lat=51.16)
        assert result["status"] == "ok"
        doc = mock_col.insert_one.call_args[0][0]
        assert doc["location"]["type"] == "Point"
        assert doc["location"]["coordinates"] == [10.45, 51.16]

    def test_event_inserts(self, mock_mongo):
        client, db = mock_mongo
        mock_col = MagicMock()
        mock_col.insert_one.return_value = MagicMock(inserted_id="evt1")
        db.__getitem__ = MagicMock(return_value=mock_col)
        db.events = mock_col
        self.store._client = client
        self.store._cols_ready = {"events", "events_geo"}

        result = self.store.event("earthquake", "Major earthquake in Turkey",
                                  {"magnitude": 7.2}, severity="critical",
                                  countries=["TUR"], region="mena")
        assert result["status"] == "ok"
        doc = mock_col.insert_one.call_args[0][0]
        assert doc["meta"]["subtype"] == "earthquake"
        assert doc["meta"]["severity"] == "critical"
        assert doc["summary"] == "Major earthquake in Turkey"

    def test_history_rejects_invalid_kind(self):
        result = self.store.history("badkind", "X")
        assert result[0]["error"]

    def test_aggregate_blocks_write_stages(self, mock_mongo):
        client, db = mock_mongo
        self.store._client = client
        self.store._cols_ready = {"snap_stocks", "snap_stocks_geo"}

        for stage in ["$out", "$merge", "$unionWith"]:
            result = self.store.aggregate("stocks", [{stage: "target"}])
            assert result[0]["error"]
            assert "blocked" in result[0]["error"]

    def test_aggregate_rejects_invalid_kind(self):
        result = self.store.aggregate("badkind", [{"$match": {}}])
        assert result[0]["error"]

    def test_archive_snapshot_rejects_invalid_kind(self):
        result = self.store.archive_snapshot("badkind", "X", "type", {})
        assert "error" in result

    def test_archive_snapshot_inserts(self, mock_mongo):
        client, db = mock_mongo
        mock_col = MagicMock()
        mock_col.insert_one.return_value = MagicMock(inserted_id="arch1")
        db.__getitem__ = MagicMock(return_value=mock_col)
        self.store._client = client
        self.store._cols_ready = {"arch_countries"}

        result = self.store.archive_snapshot("countries", "DEU", "indicators",
                                             {"gdp": 3.8}, region="europe")
        assert result["status"] == "ok"
        assert result["collection"] == "arch_countries"

    def test_compact_rejects_invalid_kind(self):
        result = self.store.compact("badkind", "X", "price")
        assert "error" in result

    def test_compact_invalid_bucket(self, mock_mongo):
        client, db = mock_mongo
        mock_col = MagicMock()
        db.__getitem__ = MagicMock(return_value=mock_col)
        self.store._client = client
        self.store._cols_ready = {"snap_stocks", "snap_stocks_geo"}

        result = self.store.compact("stocks", "AAPL", "price", bucket="decade")
        assert "error" in result
        assert "invalid bucket" in result["error"]

    def test_chart_rejects_invalid_kind(self):
        result = self.store.chart("badkind", "X", "price", ["close"])
        assert "Unknown kind" in result

    def test_nearby_rejects_invalid_kind(self):
        result = self.store.nearby("badkind", 10.0, 50.0)
        assert result[0]["error"]
