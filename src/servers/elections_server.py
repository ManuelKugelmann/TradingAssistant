"""Elections — ReliefWeb election monitoring + Google Civic Info."""
from fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("elections", description="Global elections and democracy data")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY", "")


@mcp.tool()
async def election_reports(query: str = "election", country: str = "",
                            limit: int = 20) -> dict:
    """ReliefWeb election/crisis reports."""
    params = {"appname": "mcp", "limit": limit,
              "query[value]": query, "sort[]": "date:desc"}
    if country:
        params["filter[field]"] = f"country.name:{country}"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.reliefweb.int/v1/reports", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def us_voter_info(address: str) -> dict:
    """US election info for an address (Google Civic Info API)."""
    if not GOOGLE_KEY:
        return {"error": "GOOGLE_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://www.googleapis.com/civicinfo/v2/voterInfoQuery",
                        params={"key": GOOGLE_KEY, "address": address})
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
