"""Elections — Global election data, EU Parliament, Google Civic Info, Wikidata."""
from fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("elections", instructions="Global elections and democracy data")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY", "")

_WD_HEADERS = {"User-Agent": "TradingAssistant/1.0 (trading signals research)"}


# ── Wikidata (global elections, no key) ──────────────────


@mcp.tool()
async def global_elections(country: str = "", year: str = "",
                           limit: int = 20) -> list[dict]:
    """Global elections (Wikidata). country: English name. year: e.g. '2025'."""
    filters = []
    if country:
        filters.append(f'FILTER(CONTAINS(LCASE(?countryLabel), LCASE("{country}")))')
    if year:
        filters.append(f"FILTER(YEAR(?date) = {year})")
    filter_block = "\n    ".join(filters)
    query = f"""SELECT ?election ?electionLabel ?countryLabel ?date ?typeLabel WHERE {{
  ?election wdt:P31/wdt:P279* wd:Q40231 .
  ?election wdt:P17 ?country .
  ?election wdt:P585 ?date .
  OPTIONAL {{ ?election wdt:P31 ?type }}
  {filter_block}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}} ORDER BY DESC(?date) LIMIT {limit}"""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://query.wikidata.org/sparql",
                        params={"query": query, "format": "json"},
                        headers=_WD_HEADERS)
        r.raise_for_status()
        bindings = r.json()["results"]["bindings"]
        return [{"election": b.get("electionLabel", {}).get("value", ""),
                 "country": b.get("countryLabel", {}).get("value", ""),
                 "date": b.get("date", {}).get("value", ""),
                 "type": b.get("typeLabel", {}).get("value", "")}
                for b in bindings]


@mcp.tool()
async def heads_of_state(country: str = "", limit: int = 10) -> list[dict]:
    """Heads of state/government (Wikidata). country: English name."""
    country_filter = ""
    if country:
        country_filter = f'FILTER(CONTAINS(LCASE(?countryLabel), LCASE("{country}")))'
    query = f"""SELECT ?person ?personLabel ?countryLabel ?positionLabel ?start ?end WHERE {{
  ?person wdt:P39 ?position .
  ?position wdt:P279* wd:Q48352 .
  ?person p:P39 ?stmt .
  ?stmt ps:P39 ?position .
  ?stmt pq:P580 ?start .
  OPTIONAL {{ ?stmt pq:P582 ?end }}
  ?position wdt:P17 ?country .
  {country_filter}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}} ORDER BY DESC(?start) LIMIT {limit}"""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://query.wikidata.org/sparql",
                        params={"query": query, "format": "json"},
                        headers=_WD_HEADERS)
        r.raise_for_status()
        bindings = r.json()["results"]["bindings"]
        return [{"person": b.get("personLabel", {}).get("value", ""),
                 "country": b.get("countryLabel", {}).get("value", ""),
                 "position": b.get("positionLabel", {}).get("value", ""),
                 "start": b.get("start", {}).get("value", ""),
                 "end": b.get("end", {}).get("value", "")}
                for b in bindings]


# ── EU Parliament (no key) ──────────────────────────────


@mcp.tool()
async def eu_parliament_meps(country: str = "", limit: int = 50) -> dict:
    """EU Parliament members. country: ISO2 (DE, FR, IT)."""
    params: dict = {"offset": 0, "limit": limit}
    if country:
        params["country-of-representation"] = country.upper()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://data.europarl.europa.eu/api/v2/meps",
                        params=params,
                        headers={"Accept": "application/ld+json"})
        r.raise_for_status()
        data = r.json()
        meps = data.get("data", [])
        return {"count": len(meps), "meps": meps}


@mcp.tool()
async def eu_parliament_votes(year: str = "2025", limit: int = 20) -> dict:
    """EU Parliament plenary documents/votes."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://data.europarl.europa.eu/api/v2/plenary-documents",
                        params={"year": year, "limit": limit},
                        headers={"Accept": "application/ld+json"})
        r.raise_for_status()
        return r.json()


# ── Google Civic Info (US, needs key) ────────────────────


@mcp.tool()
async def us_representatives(address: str) -> dict:
    """US elected officials for an address (Google Civic Info)."""
    if not GOOGLE_KEY:
        return {"error": "GOOGLE_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://www.googleapis.com/civicinfo/v2/representatives",
                        params={"key": GOOGLE_KEY, "address": address})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def us_voter_info(address: str) -> dict:
    """US voter/election info for an address. Only during active elections."""
    if not GOOGLE_KEY:
        return {"error": "GOOGLE_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://www.googleapis.com/civicinfo/v2/voterInfoQuery",
                        params={"key": GOOGLE_KEY, "address": address})
        r.raise_for_status()
        return r.json()


# ── ReliefWeb (election-related reports, no key) ────────


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


if __name__ == "__main__":
    mcp.run(transport="stdio")
