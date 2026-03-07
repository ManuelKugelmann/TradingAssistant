"""Transport — OpenSky flights + AIS vessel tracking."""
from fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("transport", instructions="Flight tracking and vessel positions")
AIS_KEY = os.environ.get("AISSTREAM_API_KEY", "")


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


if __name__ == "__main__":
    mcp.run(transport="stdio")
