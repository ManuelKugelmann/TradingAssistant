"""Humanitarian — UNHCR refugees, OCHA HDX, ReliefWeb reports."""
from fastmcp import FastMCP
import httpx

mcp = FastMCP("humanitarian", description="Refugee, displacement, and humanitarian data")


@mcp.tool()
async def unhcr_population(year: int = 2024, country_origin: str = "",
                            country_asylum: str = "") -> dict:
    """UNHCR refugee population. Countries as ISO3."""
    params = {"year": year, "limit": 100}
    if country_origin:
        params["coo"] = country_origin
    if country_asylum:
        params["coa"] = country_asylum
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.unhcr.org/population/v1/population/", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def hdx_search(query: str, rows: int = 20) -> dict:
    """Search Humanitarian Data Exchange datasets."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://data.humdata.org/api/3/action/package_search",
                        params={"q": query, "rows": rows})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def reliefweb_reports(query: str = "", country: str = "",
                             limit: int = 20) -> dict:
    """ReliefWeb humanitarian reports and situation updates."""
    body = {"limit": limit, "sort": ["date:desc"]}
    if query:
        body["query"] = {"value": query}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.reliefweb.int/v1/reports",
                         json=body, params={"appname": "mcp"})
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
