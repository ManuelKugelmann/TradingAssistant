"""Agriculture — FAOSTAT + USDA NASS."""
from fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("agri", description="FAO global agriculture + USDA crop data")
BASE = "https://fenixservices.fao.org/faostat/api/v1/en"
NASS_KEY = os.environ.get("USDA_NASS_API_KEY", "")


@mcp.tool()
async def fao_datasets() -> list:
    """List FAOSTAT dataset codes (QCL=crops, TP=trade, PP=prices)."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{BASE}/definitions/domain")
        r.raise_for_status()
        return [{"code": d["code"], "label": d["label"]} for d in r.json()["data"]]


@mcp.tool()
async def fao_data(domain: str = "QCL", area: str = "5000>",
                    item: str = "15", element: str = "5510",
                    year: str = "2020,2021,2022,2023") -> dict:
    """FAOSTAT data. item: 15=wheat, 56=maize, 27=rice, 236=soybean.
    element: 5510=production, 5312=area, 5419=yield."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{BASE}/data/{domain}", params={
            "area": area, "item": item, "element": element, "year": year,
            "output_type": "objects"})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def usda_crop(commodity: str, year: int = 2025,
                     state: str = "US TOTAL") -> dict:
    """USDA crop production. commodity: CORN, SOYBEANS, WHEAT, etc."""
    if not NASS_KEY:
        return {"error": "USDA_NASS_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://quickstats.nass.usda.gov/api/api_GET/", params={
            "key": NASS_KEY, "commodity_desc": commodity.upper(),
            "year": year, "agg_level_desc": "NATIONAL" if state == "US TOTAL" else "STATE",
            "statisticcat_desc": "PRODUCTION", "format": "json"})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def usda_crop_progress(commodity: str, year: int = 2025) -> dict:
    """Weekly crop progress (planted/emerged/harvested %)."""
    if not NASS_KEY:
        return {"error": "USDA_NASS_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://quickstats.nass.usda.gov/api/api_GET/", params={
            "key": NASS_KEY, "commodity_desc": commodity.upper(),
            "year": year, "source_desc": "SURVEY",
            "statisticcat_desc": "PROGRESS", "format": "json"})
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
