"""Transport & Infra — OpenSky flights, AIS vessels, Cloudflare Radar, RIPE Atlas."""
from fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("transport", instructions="Flights, vessels, internet traffic, network probes")
AIS_KEY = os.environ.get("AISSTREAM_API_KEY", "")
CF_TOKEN = os.environ.get("CF_API_TOKEN", "")


@mcp.tool()
async def flights_in_area(lat_min: float, lat_max: float,
                           lon_min: float, lon_max: float) -> dict:
    """OpenSky live aircraft in bounding box."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://opensky-network.org/api/states/all", params={
            "lamin": lat_min, "lamax": lat_max, "lomin": lon_min, "lomax": lon_max})
        r.raise_for_status()
        data = r.json()
        return {"count": len(data.get("states", [])), "states": data.get("states", [])[:50]}


@mcp.tool()
async def flight_history(icao24: str, begin: int = 0, end: int = 0) -> dict:
    """Flight history for aircraft by ICAO24 hex address."""
    async with httpx.AsyncClient(timeout=15) as c:
        params = {"icao24": icao24}
        if begin:
            params["begin"] = begin
        if end:
            params["end"] = end
        r = await c.get("https://opensky-network.org/api/flights/aircraft", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def vessels_in_area(lat_min: float, lat_max: float,
                           lon_min: float, lon_max: float) -> dict:
    """AIS vessel positions. Chokepoints: Suez 29.8,30.1,32.3,32.6 —
    Hormuz 26.0,27.0,55.5,57.0 — Panama 8.8,9.4,-79.9,-79.5."""
    if not AIS_KEY:
        return {"error": "AISSTREAM_API_KEY not set"}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://api.aisstream.io/v0/vessel-positions", params={
            "apiKey": AIS_KEY,
            "boundingBox": f"{lat_min},{lon_min},{lat_max},{lon_max}"})
        r.raise_for_status()
        return r.json()


# ── Internet Infrastructure (formerly infra_server.py) ──────────


@mcp.tool()
async def internet_traffic(location: str = "", date_range: str = "7d") -> dict:
    """Cloudflare Radar internet traffic. location: country ISO2."""
    if not CF_TOKEN:
        return {"error": "CF_API_TOKEN not set"}
    params = {"dateRange": date_range}
    if location:
        params["location"] = location
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.cloudflare.com/client/v4/radar/http/summary/http_protocol",
                        params=params,
                        headers={"Authorization": f"Bearer {CF_TOKEN}"})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def ripe_probes(country: str = "", status: int = 1,
                       limit: int = 50) -> dict:
    """RIPE Atlas probes. status: 1=connected, 2=disconnected."""
    params = {"limit": limit, "status": status}
    if country:
        params["country_code"] = country
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://atlas.ripe.net/api/v2/probes/", params=params)
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
