"""Conflict, Military & Humanitarian — UCDP, ACLED, sanctions, UNHCR, HDX, ReliefWeb."""
from fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("conflict", instructions="Armed conflict, military, sanctions, refugees, humanitarian data")
ACLED_KEY = os.environ.get("ACLED_API_KEY", "")
ACLED_EMAIL = os.environ.get("ACLED_EMAIL", "")


@mcp.tool()
async def ucdp_conflicts(year: int = 2024, page: int = 1) -> dict:
    """UCDP armed conflicts by year. Georeferenced events 1946-present."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://ucdpapi.pcr.uu.se/api/gedevents/24.1",
                        params={"pagesize": 100, "page": page, "Year": year})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def acled_events(country: str = "", event_type: str = "",
                        event_date_start: str = "", limit: int = 100) -> dict:
    """ACLED conflict/protest events. event_type: Battles, Protests, Riots,
    Violence against civilians, Explosions/Remote violence."""
    if not ACLED_KEY:
        return {"error": "ACLED_API_KEY not set"}
    params = {"key": ACLED_KEY, "email": ACLED_EMAIL, "limit": limit}
    if country:
        params["country"] = country
    if event_type:
        params["event_type"] = event_type
    if event_date_start:
        params["event_date"] = f"{event_date_start}|"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.acleddata.com/acled/read", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def search_sanctions(query: str, schema: str = "") -> dict:
    """OpenSanctions search. schema: Person, Company, Vessel, Aircraft, Organization."""
    params = {"q": query, "limit": 20}
    if schema:
        params["schema"] = schema
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.opensanctions.org/search/default", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def military_spending(country: str = "all", date: str = "2015:2024") -> dict:
    """SIPRI military expenditure (% GDP) via World Bank."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"https://api.worldbank.org/v2/country/{country}/indicator/MS.MIL.XPND.GD.ZS",
            params={"format": "json", "date": date, "per_page": 300})
        r.raise_for_status()
        return r.json()


# ── Humanitarian (formerly humanitarian_server.py) ──────────


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
    if country:
        body["filter"] = {"field": "country.name", "value": [country]}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.reliefweb.int/v1/reports",
                         json=body, params={"appname": "mcp"})
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
