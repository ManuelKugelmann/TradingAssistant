"""Internet Infrastructure — Cloudflare Radar + RIPE Atlas."""
from fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("infra", instructions="Internet traffic, outages, BGP, latency")
CF_TOKEN = os.environ.get("CF_API_TOKEN", "")


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
