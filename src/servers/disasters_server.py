"""Disasters — USGS Earthquakes + GDACS + NASA EONET."""
from fastmcp import FastMCP
import httpx
from datetime import datetime, timedelta, timezone

mcp = FastMCP("disasters", instructions="Real-time earthquakes, disasters, natural events")


@mcp.tool()
async def get_earthquakes(min_magnitude: float = 4.0, days: int = 7,
                          alert_level: str = "", limit: int = 100) -> dict:
    """Recent earthquakes. alert_level: green/yellow/orange/red or empty."""
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {"format": "geojson", "starttime": start,
              "minmagnitude": min_magnitude, "limit": limit, "orderby": "time"}
    if alert_level:
        params["alertlevel"] = alert_level
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params=params)
        r.raise_for_status()
        data = r.json()
        return {"count": data["metadata"]["count"],
                "earthquakes": [{"mag": f["properties"]["mag"],
                    "place": f["properties"]["place"],
                    "time": f["properties"]["time"],
                    "tsunami": f["properties"].get("tsunami"),
                    "alert": f["properties"].get("alert"),
                    "coords": f["geometry"]["coordinates"]}
                    for f in data["features"]]}


@mcp.tool()
async def get_disasters() -> dict:
    """GDACS global disaster alerts (earthquakes, floods, cyclones, volcanoes)."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH",
                        params={"eventlist": "", "fromDate": "", "toDate": "", "alertlevel": ""})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def get_natural_events(category: str = "", days: int = 30,
                              status: str = "open", limit: int = 50) -> dict:
    """NASA EONET natural events. category: wildfires, severeStorms, volcanoes,
    seaLakeIce, earthquakes, floods, landslides, drought, dustHaze, snow."""
    params = {"status": status, "limit": limit, "days": days}
    if category:
        params["category"] = category
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://eonet.gsfc.nasa.gov/api/v3/events", params=params)
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
