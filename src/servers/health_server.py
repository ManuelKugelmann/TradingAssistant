"""Health — WHO GHO, WHO Outbreaks, disease.sh, OpenFDA."""
from fastmcp import FastMCP
import httpx
import re

mcp = FastMCP("health", instructions="Global health, disease outbreaks, FDA data")

_SAFE_ODATA = re.compile(r'^[A-Za-z0-9_-]+$')


@mcp.tool()
async def who_indicator(indicator: str = "NCDMORT3070",
                        country: str = "", year: str = "") -> dict:
    """WHO health indicator. Examples: WHOSIS_000001 (life expectancy),
    MDG_0000000001 (under-5 mortality), WHS4_100 (hospital beds),
    NCD_BMI_30A (obesity)."""
    url = f"https://ghoapi.azureedge.net/api/{indicator}"
    params = {}
    filters = []
    if country:
        if not _SAFE_ODATA.match(country):
            return {"error": "invalid country code"}
        filters.append(f"SpatialDim eq '{country}'")
    if year:
        if not _SAFE_ODATA.match(year):
            return {"error": "invalid year"}
        filters.append(f"TimeDim eq {year}")
    if filters:
        params["$filter"] = " and ".join(filters)
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def disease_outbreaks(limit: int = 20) -> dict:
    """Latest WHO Disease Outbreak News."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://www.who.int/api/news/diseaseoutbreaknews",
                        params={"sf_culture": "en", "$top": limit,
                                "$orderby": "PublicationDate desc"})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def disease_tracker(disease: str = "covid", country: str = "") -> dict:
    """Real-time disease tracking (disease.sh). disease: covid/influenza."""
    async with httpx.AsyncClient(timeout=30) as c:
        if disease == "covid":
            url = f"https://disease.sh/v3/covid-19/{'countries/' + country if country else 'all'}"
        else:
            url = f"https://disease.sh/v3/influenza/{'ihsa/country/' + country if country else 'ihsa'}"
        r = await c.get(url)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def fda_adverse_events(drug: str = "", limit: int = 20) -> dict:
    """FDA adverse drug event reports."""
    search = f'patient.drug.medicinalproduct:"{drug}"' if drug else ""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.fda.gov/drug/event.json",
                        params={"search": search, "limit": limit})
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
