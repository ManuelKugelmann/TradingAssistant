"""Integration tests for free (no API key) endpoints.

These hit real public APIs. Marked with pytest.mark.integration so they
are skipped in normal CI and only run in the integration job.
"""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

# Allow importing server modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "servers"))

pytestmark = pytest.mark.integration

# ── helpers ──────────────────────────────────────────────


def run(coro):
    """Run an async tool function synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── weather_server (Open-Meteo, NOAA) ───────────────────


class TestWeather:
    @pytest.fixture(autouse=True)
    def _load(self):
        import weather_server as mod
        self.m = mod

    def test_forecast_returns_daily(self):
        result = run(self.m.forecast(lat=48.14, lon=11.58, days=2))
        assert "daily" in result
        assert "temperature_2m_max" in result["daily"]

    def test_historical_weather(self):
        result = run(self.m.historical_weather(
            lat=48.14, lon=11.58, start="2024-06-01", end="2024-06-07"))
        assert "daily" in result

    def test_flood_forecast(self):
        result = run(self.m.flood_forecast(lat=48.14, lon=11.58, days=3))
        assert "daily" in result

    def test_space_weather(self):
        result = run(self.m.space_weather())
        assert "kp_index" in result
        assert "solar_wind" in result
        assert "alerts" in result


# ── disasters_server (USGS, NASA EONET) ─────────────────


class TestDisasters:
    @pytest.fixture(autouse=True)
    def _load(self):
        import disasters_server as mod
        self.m = mod

    def test_earthquakes(self):
        result = run(self.m.get_earthquakes(min_magnitude=5.0, days=30, limit=5))
        assert "count" in result
        assert "earthquakes" in result
        assert isinstance(result["earthquakes"], list)

    def test_natural_events(self):
        result = run(self.m.get_natural_events(days=60, limit=5))
        assert "events" in result or "title" in result


# ── health_server (WHO GHO, OpenFDA) ────────────────────


class TestHealth:
    @pytest.fixture(autouse=True)
    def _load(self):
        import health_server as mod
        self.m = mod

    def test_who_indicator(self):
        result = run(self.m.who_indicator(
            indicator="WHOSIS_000001", country="DEU", year="2019"))
        assert "value" in result

    def test_fda_adverse_events(self):
        result = run(self.m.fda_adverse_events(drug="aspirin", limit=3))
        assert "results" in result or "meta" in result


# ── macro_server (World Bank, IMF) ──────────────────────


class TestMacroFree:
    @pytest.fixture(autouse=True)
    def _load(self):
        import macro_server as mod
        self.m = mod

    def test_worldbank_indicator(self):
        result = run(self.m.worldbank_indicator(
            indicator="SP.POP.TOTL", country="DEU", date="2020:2022", per_page=10))
        assert isinstance(result, list)
        assert len(result) >= 2  # World Bank returns [meta, data]

    def test_worldbank_search(self):
        result = run(self.m.worldbank_search(query="GDP"))
        assert isinstance(result, list)

    def test_imf_data(self):
        result = run(self.m.imf_data(
            database="IFS", frequency="A", ref_area="US",
            indicator="NGDP_R_XDC", start="2020", end="2022"))
        assert "CompactData" in result or "DataSet" in result or "dataSets" in result


# ── agri_server (FAOSTAT) ───────────────────────────────


class TestAgriFree:
    @pytest.fixture(autouse=True)
    def _load(self):
        import agri_server as mod
        self.m = mod

    def test_fao_datasets(self):
        result = run(self.m.fao_datasets())
        assert isinstance(result, list)
        assert len(result) > 0
        assert "code" in result[0]

    def test_fao_data(self):
        result = run(self.m.fao_data(
            domain="QCL", area="5000>", item="15",
            element="5510", year="2022"))
        assert "data" in result


# ── conflict_server (UCDP, OpenSanctions, World Bank military) ───


class TestConflictFree:
    @pytest.fixture(autouse=True)
    def _load(self):
        import conflict_server as mod
        self.m = mod

    def test_ucdp_conflicts(self):
        result = run(self.m.ucdp_conflicts(year=2023, page=1))
        assert "Result" in result or "result" in result or isinstance(result, dict)

    def test_search_sanctions(self):
        result = run(self.m.search_sanctions(query="Gazprom"))
        assert "results" in result or "result" in result

    def test_military_spending(self):
        result = run(self.m.military_spending(country="USA", date="2020:2022"))
        assert isinstance(result, list)


# ── elections_server (ReliefWeb) ─────────────────────────


class TestElectionsFree:
    @pytest.fixture(autouse=True)
    def _load(self):
        import elections_server as mod
        self.m = mod

    def test_election_reports(self):
        result = run(self.m.election_reports(query="election", limit=3))
        assert "data" in result


# ── humanitarian_server (UNHCR, HDX, ReliefWeb) ─────────


class TestHumanitarian:
    @pytest.fixture(autouse=True)
    def _load(self):
        import humanitarian_server as mod
        self.m = mod

    def test_unhcr_population(self):
        result = run(self.m.unhcr_population(year=2023))
        assert isinstance(result, (dict, list))

    def test_hdx_search(self):
        result = run(self.m.hdx_search(query="food security", rows=3))
        assert "result" in result or "success" in result

    def test_reliefweb_reports(self):
        result = run(self.m.reliefweb_reports(query="drought", limit=3))
        assert "data" in result


# ── infra_server (RIPE Atlas — free) ────────────────────


class TestInfraFree:
    @pytest.fixture(autouse=True)
    def _load(self):
        import infra_server as mod
        self.m = mod

    def test_ripe_probes(self):
        result = run(self.m.ripe_probes(country="DE", limit=5))
        assert "results" in result or "objects" in result


# ── water_server (USGS, Drought Monitor) ────────────────


class TestWater:
    @pytest.fixture(autouse=True)
    def _load(self):
        import water_server as mod
        self.m = mod

    def test_streamflow(self):
        # Use a known USGS site
        result = run(self.m.streamflow(site="01646500", period="P1D"))
        assert "value" in result

    def test_drought(self):
        result = run(self.m.drought(area_type="state", area="CA"))
        assert isinstance(result, (dict, list))


# ── transport_server (OpenSky — free) ───────────────────


class TestTransportFree:
    @pytest.fixture(autouse=True)
    def _load(self):
        import transport_server as mod
        self.m = mod

    def test_flights_in_area(self):
        # Small bounding box over Frankfurt airport
        result = run(self.m.flights_in_area(
            lat_min=50.0, lat_max=50.1, lon_min=8.5, lon_max=8.6))
        assert "count" in result
        assert "states" in result
