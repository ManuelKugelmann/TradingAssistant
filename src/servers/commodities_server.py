"""Commodities — UN Comtrade trade flows + EIA energy data."""
from fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("commodities", description="UN trade flows, EIA energy data")
COMTRADE_KEY = os.environ.get("COMTRADE_API_KEY", "")
EIA_KEY = os.environ.get("EIA_API_KEY", "")


@mcp.tool()
async def trade_flows(reporter: str = "842", partner: str = "0",
                      commodity: str = "TOTAL", flow: str = "M",
                      period: str = "2023") -> dict:
    """UN Comtrade trade flows. reporter/partner: M49 codes (842=USA, 156=China,
    276=Germany, 0=World). flow: M(import), X(export)."""
    if not COMTRADE_KEY:
        return {"error": "COMTRADE_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://comtradeapi.un.org/data/v1/get/C/A/HS", params={
            "reporterCode": reporter, "partnerCode": partner,
            "cmdCode": commodity, "flowCode": flow, "period": period,
            "subscription-key": COMTRADE_KEY})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def energy_series(series: str = "PET.RWTC.D",
                         start: str = "2024-01",
                         frequency: str = "monthly") -> dict:
    """EIA energy data. series: PET.RWTC.D (WTI crude), PET.RBRTE.D (Brent),
    NG.RNGWHHD.D (Henry Hub natgas), PET.WCRSTUS1.W (US crude stocks),
    ELEC.GEN.ALL-US-99.M (US electricity)."""
    if not EIA_KEY:
        return {"error": "EIA_API_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"https://api.eia.gov/v2/seriesid/{series}",
                        params={"api_key": EIA_KEY, "start": start,
                                "frequency": frequency})
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
