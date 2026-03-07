"""Macro — FRED, World Bank, IMF SDMX."""
from fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("macro", instructions="Macroeconomic indicators: FRED, World Bank, IMF")
FRED_KEY = os.environ.get("FRED_API_KEY", "")


@mcp.tool()
async def fred_series(series_id: str, limit: int = 100,
                      sort_order: str = "desc") -> dict:
    """FRED time series. Examples: GDP, UNRATE, CPIAUCSL, DFF (fed funds),
    T10Y2Y (yield curve), M2SL (money supply), VIXCLS, ICSA (jobless claims)."""
    if not FRED_KEY:
        return {"error": "FRED_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.stlouisfed.org/fred/series/observations", params={
            "series_id": series_id, "api_key": FRED_KEY,
            "file_type": "json", "limit": limit, "sort_order": sort_order})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def fred_search(query: str, limit: int = 20) -> dict:
    """Search FRED for economic data series."""
    if not FRED_KEY:
        return {"error": "FRED_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.stlouisfed.org/fred/series/search", params={
            "search_text": query, "api_key": FRED_KEY,
            "file_type": "json", "limit": limit})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def worldbank_indicator(indicator: str = "NY.GDP.MKTP.CD",
                               country: str = "all", date: str = "2020:2024",
                               per_page: int = 100) -> dict:
    """World Bank indicator. Examples: NY.GDP.MKTP.CD (GDP), SP.POP.TOTL (population),
    FP.CPI.TOTL.ZG (inflation), SL.UEM.TOTL.ZS (unemployment),
    MS.MIL.XPND.GD.ZS (military spending % GDP)."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}",
            params={"format": "json", "date": date, "per_page": per_page})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def worldbank_search(query: str) -> dict:
    """Search World Bank indicators by keyword."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.worldbank.org/v2/indicator",
                        params={"format": "json", "qterm": query, "per_page": 50})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def imf_data(database: str = "IFS", frequency: str = "A",
                    ref_area: str = "US", indicator: str = "NGDP_R_XDC",
                    start: str = "2020", end: str = "2024") -> dict:
    """IMF SDMX. database: IFS, BOP, DOT, WEO.
    indicator: NGDP_R_XDC (real GDP), PCPI_IX (CPI), ENDA_XDC_USD_RATE (exchange)."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/"
            f"{database}/{frequency}.{ref_area}.{indicator}",
            params={"startPeriod": start, "endPeriod": end})
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
