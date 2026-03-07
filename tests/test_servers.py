"""Tests for the 12 domain MCP servers.

Each server is an async httpx-based tool. Tests mock httpx.AsyncClient to verify:
- Correct URL/param construction
- API key checks (return error dict when missing)
- Response transformation (e.g., earthquake flattening)
- Input validation (e.g., health _SAFE_ODATA)
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add servers dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "servers"))


# ── Helpers ──────────────────────────────────────

def _mock_response(data, status_code=200):
    """Create a mock httpx.Response.

    httpx.Response.json() and .raise_for_status() are sync methods,
    so we use MagicMock (not AsyncMock) for those.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    if status_code >= 400:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


def _patch_httpx_get(response):
    """Return a patch context for httpx.AsyncClient that returns response on get()."""
    client = AsyncMock()
    client.get.return_value = response
    client.post.return_value = response
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return patch("httpx.AsyncClient", return_value=client), client


# ── Weather Server ────────────────────────────────


class TestWeatherServer:
    @pytest.fixture(autouse=True)
    def _import(self):
        import weather_server
        self.mod = weather_server

    @pytest.mark.asyncio
    async def test_forecast_calls_open_meteo(self):
        resp = _mock_response({"daily": {"temperature_2m_max": [20]}})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            result = await self.mod.forecast(lat=52.5, lon=13.4, days=3)
        assert result["daily"]["temperature_2m_max"] == [20]
        url = client.get.call_args[0][0]
        assert "open-meteo.com" in url
        assert client.get.call_args[1]["params"]["forecast_days"] == 3

    @pytest.mark.asyncio
    async def test_historical_weather_params(self):
        resp = _mock_response({"daily": {}})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.historical_weather(lat=40, lon=-74, start="2023-01-01", end="2023-12-31")
        params = client.get.call_args[1]["params"]
        assert params["start_date"] == "2023-01-01"
        assert params["end_date"] == "2023-12-31"

    @pytest.mark.asyncio
    async def test_flood_forecast(self):
        resp = _mock_response({"daily": {"river_discharge": [100]}})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            result = await self.mod.flood_forecast(lat=51, lon=7)
        assert "daily" in result
        assert "flood-api.open-meteo.com" in client.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_space_weather_aggregates(self):
        kp_resp = _mock_response([{"kp": 3}] * 10)
        solar_resp = _mock_response([{"speed": 400}] * 10)
        alerts_resp = _mock_response([{"alert": "G1"}] * 3)
        client = AsyncMock()
        client.get = AsyncMock(side_effect=[kp_resp, solar_resp, alerts_resp])
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=client):
            result = await self.mod.space_weather()
        assert len(result["kp_index"]) == 5
        assert len(result["solar_wind"]) == 5
        assert len(result["alerts"]) == 3


# ── Macro Server ──────────────────────────────────


class TestMacroServer:
    @pytest.fixture(autouse=True)
    def _import(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "test_key")
        # Reimport to pick up env
        if "macro_server" in sys.modules:
            del sys.modules["macro_server"]
        import macro_server
        self.mod = macro_server

    @pytest.mark.asyncio
    async def test_fred_missing_key(self, monkeypatch):
        monkeypatch.setattr(self.mod, "FRED_KEY", "")
        result = await self.mod.fred_series("GDP")
        assert result["error"] == "FRED_API_KEY not set"

    @pytest.mark.asyncio
    async def test_fred_series_params(self):
        resp = _mock_response({"observations": [{"value": "100"}]})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            result = await self.mod.fred_series("UNRATE", limit=50)
        params = client.get.call_args[1]["params"]
        assert params["series_id"] == "UNRATE"
        assert params["limit"] == 50

    @pytest.mark.asyncio
    async def test_worldbank_indicator(self):
        resp = _mock_response([{}, [{"value": 4000}]])
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            result = await self.mod.worldbank_indicator(country="DEU")
        url = client.get.call_args[0][0]
        assert "DEU" in url
        assert "worldbank.org" in url

    @pytest.mark.asyncio
    async def test_imf_data_url(self):
        resp = _mock_response({"data": {}})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.imf_data(database="IFS", ref_area="DE", indicator="NGDP_R_XDC")
        url = client.get.call_args[0][0]
        assert "IFS" in url
        assert "DE" in url
        assert "NGDP_R_XDC" in url


# ── Disasters Server ─────────────────────────────


class TestDisastersServer:
    @pytest.fixture(autouse=True)
    def _import(self):
        import disasters_server
        self.mod = disasters_server

    @pytest.mark.asyncio
    async def test_earthquakes_transform(self):
        raw = {
            "metadata": {"count": 1},
            "features": [{
                "properties": {"mag": 5.2, "place": "Tokyo", "time": 1234567890,
                               "tsunami": 0, "alert": "green"},
                "geometry": {"coordinates": [139.7, 35.7, 10]}
            }]
        }
        resp = _mock_response(raw)
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            result = await self.mod.get_earthquakes(min_magnitude=4.0, days=7)
        assert result["count"] == 1
        assert result["earthquakes"][0]["mag"] == 5.2
        assert result["earthquakes"][0]["place"] == "Tokyo"
        assert result["earthquakes"][0]["coords"] == [139.7, 35.7, 10]

    @pytest.mark.asyncio
    async def test_earthquakes_alert_filter(self):
        raw = {"metadata": {"count": 0}, "features": []}
        resp = _mock_response(raw)
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.get_earthquakes(alert_level="red")
        params = client.get.call_args[1]["params"]
        assert params["alertlevel"] == "red"

    @pytest.mark.asyncio
    async def test_natural_events_category(self):
        resp = _mock_response({"events": []})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.get_natural_events(category="wildfires", days=14)
        params = client.get.call_args[1]["params"]
        assert params["category"] == "wildfires"
        assert params["days"] == 14


# ── Health Server ─────────────────────────────────


class TestHealthServer:
    @pytest.fixture(autouse=True)
    def _import(self):
        import health_server
        self.mod = health_server

    def test_safe_odata_regex(self):
        assert self.mod._SAFE_ODATA.match("DEU")
        assert self.mod._SAFE_ODATA.match("2024")
        assert not self.mod._SAFE_ODATA.match("'; DROP TABLE --")
        assert not self.mod._SAFE_ODATA.match("a b")
        assert not self.mod._SAFE_ODATA.match("")

    @pytest.mark.asyncio
    async def test_who_rejects_injection(self):
        result = await self.mod.who_indicator(country="'; DROP TABLE")
        assert result["error"] == "invalid country code"

    @pytest.mark.asyncio
    async def test_who_rejects_invalid_year(self):
        result = await self.mod.who_indicator(year="2024; DROP")
        assert result["error"] == "invalid year"

    @pytest.mark.asyncio
    async def test_who_indicator_builds_filter(self):
        resp = _mock_response({"value": []})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.who_indicator(indicator="WHOSIS_000001", country="DEU", year="2022")
        params = client.get.call_args[1]["params"]
        assert "SpatialDim eq 'DEU'" in params["$filter"]
        assert "TimeDim eq 2022" in params["$filter"]

    @pytest.mark.asyncio
    async def test_disease_tracker_covid_url(self):
        resp = _mock_response({"cases": 1000})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.disease_tracker(disease="covid", country="Germany")
        url = client.get.call_args[0][0]
        assert "covid-19" in url
        assert "Germany" in url

    @pytest.mark.asyncio
    async def test_disease_tracker_all(self):
        resp = _mock_response({"cases": 1000})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.disease_tracker(disease="covid")
        url = client.get.call_args[0][0]
        assert url.endswith("/all")


# ── Agri Server ───────────────────────────────────


class TestAgriServer:
    @pytest.fixture(autouse=True)
    def _import(self, monkeypatch):
        monkeypatch.setenv("USDA_NASS_API_KEY", "test_key")
        if "agri_server" in sys.modules:
            del sys.modules["agri_server"]
        import agri_server
        self.mod = agri_server

    @pytest.mark.asyncio
    async def test_fao_datasets_transforms(self):
        raw = {"data": [{"code": "QCL", "label": "Crops"}, {"code": "TP", "label": "Trade"}]}
        resp = _mock_response(raw)
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            result = await self.mod.fao_datasets()
        assert result == [{"code": "QCL", "label": "Crops"}, {"code": "TP", "label": "Trade"}]

    @pytest.mark.asyncio
    async def test_usda_missing_key(self, monkeypatch):
        monkeypatch.setattr(self.mod, "NASS_KEY", "")
        result = await self.mod.usda_crop("CORN")
        assert result["error"] == "USDA_NASS_API_KEY not set"

    @pytest.mark.asyncio
    async def test_usda_crop_uppercases(self):
        resp = _mock_response({"data": []})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.usda_crop("corn")
        params = client.get.call_args[1]["params"]
        assert params["commodity_desc"] == "CORN"


# ── Commodities Server ───────────────────────────


class TestCommoditiesServer:
    @pytest.fixture(autouse=True)
    def _import(self, monkeypatch):
        monkeypatch.setenv("COMTRADE_API_KEY", "test_ct_key")
        monkeypatch.setenv("EIA_API_KEY", "test_eia_key")
        if "commodities_server" in sys.modules:
            del sys.modules["commodities_server"]
        import commodities_server
        self.mod = commodities_server

    @pytest.mark.asyncio
    async def test_trade_flows_missing_key(self, monkeypatch):
        monkeypatch.setattr(self.mod, "COMTRADE_KEY", "")
        result = await self.mod.trade_flows()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_energy_series_missing_key(self, monkeypatch):
        monkeypatch.setattr(self.mod, "EIA_KEY", "")
        result = await self.mod.energy_series()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_energy_series_url(self):
        resp = _mock_response({"response": {"data": []}})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.energy_series(series="PET.RWTC.D")
        url = client.get.call_args[0][0]
        assert "PET.RWTC.D" in url


# ── Conflict Server ──────────────────────────────


class TestConflictServer:
    @pytest.fixture(autouse=True)
    def _import(self, monkeypatch):
        monkeypatch.setenv("ACLED_API_KEY", "test_acled")
        monkeypatch.setenv("ACLED_EMAIL", "test@test.com")
        if "conflict_server" in sys.modules:
            del sys.modules["conflict_server"]
        import conflict_server
        self.mod = conflict_server

    @pytest.mark.asyncio
    async def test_acled_missing_key(self, monkeypatch):
        monkeypatch.setattr(self.mod, "ACLED_KEY", "")
        result = await self.mod.acled_events()
        assert result["error"] == "ACLED_API_KEY not set"

    @pytest.mark.asyncio
    async def test_acled_date_filter(self):
        resp = _mock_response({"data": []})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.acled_events(event_date_start="2024-01-01")
        params = client.get.call_args[1]["params"]
        assert params["event_date"] == "2024-01-01|"

    @pytest.mark.asyncio
    async def test_sanctions_missing_key(self, monkeypatch):
        monkeypatch.setattr(self.mod, "OPENSANCTIONS_KEY", "")
        result = await self.mod.search_sanctions("Putin")
        assert result["error"] == "OPENSANCTIONS_API_KEY not set"

    @pytest.mark.asyncio
    async def test_sanctions_search(self, monkeypatch):
        monkeypatch.setattr(self.mod, "OPENSANCTIONS_KEY", "test_key")
        resp = _mock_response({"results": []})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.search_sanctions("Putin", schema="Person")
        params = client.get.call_args[1]["params"]
        assert params["q"] == "Putin"
        assert params["schema"] == "Person"

    @pytest.mark.asyncio
    async def test_military_spending_url(self):
        resp = _mock_response([{}, []])
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.military_spending(country="DEU")
        url = client.get.call_args[0][0]
        assert "DEU" in url
        assert "MS.MIL.XPND.GD.ZS" in url


# ── Elections Server ─────────────────────────────


class TestElectionsServer:
    @pytest.fixture(autouse=True)
    def _import(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test_google")
        if "elections_server" in sys.modules:
            del sys.modules["elections_server"]
        import elections_server
        self.mod = elections_server

    @pytest.mark.asyncio
    async def test_election_reports_country(self):
        resp = _mock_response({"data": []})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.election_reports(query="election", country="Kenya")
        params = client.get.call_args[1]["params"]
        assert "Kenya" in params["filter[field]"]

    @pytest.mark.asyncio
    async def test_voter_info_missing_key(self, monkeypatch):
        monkeypatch.setattr(self.mod, "GOOGLE_KEY", "")
        result = await self.mod.us_voter_info("123 Main St")
        assert result["error"] == "GOOGLE_API_KEY not set"


# ── Humanitarian Server ──────────────────────────


class TestHumanitarianServer:
    @pytest.fixture(autouse=True)
    def _import(self):
        import humanitarian_server
        self.mod = humanitarian_server

    @pytest.mark.asyncio
    async def test_unhcr_filters(self):
        resp = _mock_response({"items": []})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.unhcr_population(country_origin="SYR", country_asylum="DEU")
        params = client.get.call_args[1]["params"]
        assert params["coo"] == "SYR"
        assert params["coa"] == "DEU"

    @pytest.mark.asyncio
    async def test_reliefweb_uses_post(self):
        resp = _mock_response({"data": []})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.reliefweb_reports(query="flood", country="Bangladesh")
        # Should use POST
        client.post.assert_called_once()
        body = client.post.call_args[1]["json"]
        assert body["query"]["value"] == "flood"
        assert body["filter"]["value"] == ["Bangladesh"]


# ── Infra Server ─────────────────────────────────


class TestInfraServer:
    @pytest.fixture(autouse=True)
    def _import(self, monkeypatch):
        monkeypatch.setenv("CF_API_TOKEN", "test_cf")
        if "infra_server" in sys.modules:
            del sys.modules["infra_server"]
        import infra_server
        self.mod = infra_server

    @pytest.mark.asyncio
    async def test_internet_traffic_missing_key(self, monkeypatch):
        monkeypatch.setattr(self.mod, "CF_TOKEN", "")
        result = await self.mod.internet_traffic()
        assert result["error"] == "CF_API_TOKEN not set"

    @pytest.mark.asyncio
    async def test_internet_traffic_auth_header(self):
        resp = _mock_response({"result": {}})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.internet_traffic(location="DE")
        headers = client.get.call_args[1]["headers"]
        assert "Bearer" in headers["Authorization"]

    @pytest.mark.asyncio
    async def test_ripe_probes_params(self):
        resp = _mock_response({"results": []})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.ripe_probes(country="US", status=2)
        params = client.get.call_args[1]["params"]
        assert params["country_code"] == "US"
        assert params["status"] == 2


# ── Transport Server ─────────────────────────────


class TestTransportServer:
    @pytest.fixture(autouse=True)
    def _import(self, monkeypatch):
        monkeypatch.setenv("AISSTREAM_API_KEY", "test_ais")
        if "transport_server" in sys.modules:
            del sys.modules["transport_server"]
        import transport_server
        self.mod = transport_server

    @pytest.mark.asyncio
    async def test_flights_in_area_truncates(self):
        states = [[f"plane_{i}"] for i in range(100)]
        resp = _mock_response({"states": states})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            result = await self.mod.flights_in_area(
                lat_min=40, lat_max=42, lon_min=-75, lon_max=-73
            )
        assert result["count"] == 100
        assert len(result["states"]) == 50  # truncated

    @pytest.mark.asyncio
    async def test_vessels_missing_key(self, monkeypatch):
        monkeypatch.setattr(self.mod, "AIS_KEY", "")
        result = await self.mod.vessels_in_area(
            lat_min=29.8, lat_max=30.1, lon_min=32.3, lon_max=32.6
        )
        assert result["error"] == "AISSTREAM_API_KEY not set"

    @pytest.mark.asyncio
    async def test_flight_history_params(self):
        resp = _mock_response([])
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.flight_history(icao24="abc123", begin=1000, end=2000)
        params = client.get.call_args[1]["params"]
        assert params["icao24"] == "abc123"
        assert params["begin"] == 1000
        assert params["end"] == 2000


# ── Water Server ─────────────────────────────────


class TestWaterServer:
    @pytest.fixture(autouse=True)
    def _import(self):
        import water_server
        self.mod = water_server

    @pytest.mark.asyncio
    async def test_streamflow_by_site(self):
        resp = _mock_response({"value": {"timeSeries": []}})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.streamflow(site="01646500")
        params = client.get.call_args[1]["params"]
        assert params["sites"] == "01646500"
        assert "stateCd" not in params

    @pytest.mark.asyncio
    async def test_streamflow_by_state(self):
        resp = _mock_response({"value": {}})
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.streamflow(state="TX")
        params = client.get.call_args[1]["params"]
        assert params["stateCd"] == "TX"

    @pytest.mark.asyncio
    async def test_drought_params(self):
        resp = _mock_response([])
        patcher, client = _patch_httpx_get(resp)
        with patcher:
            await self.mod.drought(area_type="county", area="06037")
        params = client.get.call_args[1]["params"]
        assert params["area_type"] == "county"
        assert params["area"] == "06037"
