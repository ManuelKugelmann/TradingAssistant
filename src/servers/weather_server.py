"""Weather, Climate & Water — Open-Meteo + NOAA SWPC + USGS Water + US Drought."""
from fastmcp import FastMCP
import httpx

mcp = FastMCP("weather", instructions="Weather, climate, space weather, water levels, drought")


@mcp.tool()
async def forecast(lat: float, lon: float, days: int = 7) -> dict:
    """Weather forecast (daily temp, precip, wind)."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "forecast_days": days,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
            "timezone": "auto"})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def historical_weather(lat: float, lon: float,
                              start: str = "2024-01-01",
                              end: str = "2024-12-31") -> dict:
    """Historical weather since 1940. start/end: YYYY-MM-DD."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": lat, "longitude": lon,
            "start_date": start, "end_date": end,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto"})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def flood_forecast(lat: float, lon: float, days: int = 7) -> dict:
    """River discharge forecast (flood risk)."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://flood-api.open-meteo.com/v1/flood", params={
            "latitude": lat, "longitude": lon, "forecast_days": days,
            "daily": "river_discharge"})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def space_weather() -> dict:
    """Space weather: Kp index, solar wind, geomagnetic storms (NOAA SWPC)."""
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            kp = await c.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json")
            solar = await c.get("https://services.swpc.noaa.gov/json/solar_wind/plasma-7-day.json")
            alerts = await c.get("https://services.swpc.noaa.gov/json/alerts.json")
            return {
                "kp_index": kp.json()[-5:] if kp.status_code == 200 else [],
                "solar_wind": solar.json()[-5:] if solar.status_code == 200 else [],
                "alerts": alerts.json()[:10] if alerts.status_code == 200 else [],
            }
    except httpx.HTTPError as e:
        return {"error": f"NOAA SWPC request failed: {e}"}


# ── Water (formerly water_server.py) ──────────────────


@mcp.tool()
async def streamflow(site: str = "", state: str = "CA",
                     period: str = "P7D") -> dict:
    """USGS real-time streamflow. period: P1D, P7D, P30D."""
    params = {"format": "json", "period": period, "parameterCd": "00060"}
    if site:
        params["sites"] = site
    elif state:
        params["stateCd"] = state
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://waterservices.usgs.gov/nwis/iv", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def drought(area_type: str = "state", area: str = "CA") -> dict:
    """US Drought Monitor. area_type: state/county/national."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://usdm.unl.edu/DmData/TimeSeries.aspx",
                        params={"area_type": area_type, "area": area, "format": "json"})
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
