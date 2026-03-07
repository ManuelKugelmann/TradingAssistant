"""Integration tests for API-key-gated endpoints.

Each test class is skipped unless the required env var is set.
Marked with pytest.mark.integration to exclude from normal CI.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "servers"))

pytestmark = pytest.mark.integration


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── FRED (macro_server) ─────────────────────────────────

@pytest.mark.skipif(not os.environ.get("FRED_API_KEY"), reason="FRED_API_KEY not set")
class TestFred:
    @pytest.fixture(autouse=True)
    def _load(self):
        import macro_server as mod
        self.m = mod

    def test_fred_series(self):
        result = run(self.m.fred_series(series_id="GDP", limit=5))
        assert "observations" in result

    def test_fred_search(self):
        result = run(self.m.fred_search(query="unemployment", limit=3))
        assert "seriess" in result


# ── EIA (commodities_server) ────────────────────────────

@pytest.mark.skipif(not os.environ.get("EIA_API_KEY"), reason="EIA_API_KEY not set")
class TestEIA:
    @pytest.fixture(autouse=True)
    def _load(self):
        import commodities_server as mod
        self.m = mod

    def test_energy_series(self):
        result = run(self.m.energy_series(
            series="PET.RWTC.D", start="2024-01", frequency="monthly"))
        assert "response" in result or "data" in result


# ── UN Comtrade (commodities_server) ────────────────────

@pytest.mark.skipif(not os.environ.get("COMTRADE_API_KEY"), reason="COMTRADE_API_KEY not set")
class TestComtrade:
    @pytest.fixture(autouse=True)
    def _load(self):
        import commodities_server as mod
        self.m = mod

    def test_trade_flows(self):
        result = run(self.m.trade_flows(
            reporter="842", partner="0", commodity="TOTAL",
            flow="M", period="2022"))
        assert "data" in result or "dataset" in result


# ── ACLED (conflict_server) ─────────────────────────────

@pytest.mark.skipif(not os.environ.get("ACLED_API_KEY"), reason="ACLED_API_KEY not set")
class TestACLED:
    @pytest.fixture(autouse=True)
    def _load(self):
        import conflict_server as mod
        self.m = mod

    def test_acled_events(self):
        result = run(self.m.acled_events(country="Ukraine", limit=5))
        assert "data" in result or "error" not in result


# ── USDA NASS (agri_server) ─────────────────────────────

@pytest.mark.skipif(not os.environ.get("USDA_NASS_API_KEY"), reason="USDA_NASS_API_KEY not set")
class TestUSDA:
    @pytest.fixture(autouse=True)
    def _load(self):
        import agri_server as mod
        self.m = mod

    def test_usda_crop(self):
        result = run(self.m.usda_crop(commodity="CORN", year=2023))
        assert "data" in result or "error" not in result

    def test_usda_crop_progress(self):
        result = run(self.m.usda_crop_progress(commodity="CORN", year=2023))
        assert "data" in result or "error" not in result


# ── Google Civic (elections_server) ──────────────────────

@pytest.mark.skipif(not os.environ.get("GOOGLE_API_KEY"), reason="GOOGLE_API_KEY not set")
class TestGoogleCivic:
    @pytest.fixture(autouse=True)
    def _load(self):
        import elections_server as mod
        self.m = mod

    def test_us_voter_info(self):
        result = run(self.m.us_voter_info(address="1600 Pennsylvania Ave NW, Washington DC"))
        assert isinstance(result, dict)


# ── Cloudflare Radar (infra_server) ─────────────────────

@pytest.mark.skipif(not os.environ.get("CF_API_TOKEN"), reason="CF_API_TOKEN not set")
class TestCloudflare:
    @pytest.fixture(autouse=True)
    def _load(self):
        import infra_server as mod
        self.m = mod

    def test_internet_traffic(self):
        result = run(self.m.internet_traffic(location="DE", date_range="1d"))
        assert "result" in result or "success" in result


# ── AIS Stream (transport_server) ───────────────────────

@pytest.mark.skipif(not os.environ.get("AISSTREAM_API_KEY"), reason="AISSTREAM_API_KEY not set")
class TestAIS:
    @pytest.fixture(autouse=True)
    def _load(self):
        import transport_server as mod
        self.m = mod

    def test_vessels_in_area(self):
        # Suez Canal chokepoint
        result = run(self.m.vessels_in_area(
            lat_min=29.8, lat_max=30.1, lon_min=32.3, lon_max=32.6))
        assert isinstance(result, (dict, list))
