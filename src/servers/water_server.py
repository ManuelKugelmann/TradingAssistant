"""Water — USGS streamflow + US Drought Monitor."""
from fastmcp import FastMCP
import httpx

mcp = FastMCP("water", description="US water levels, drought, flood monitoring")


@mcp.tool()
async def streamflow(site: str = "", state: str = "CA",
                     period: str = "P7D") -> dict:
    """USGS real-time streamflow. period: P1D, P7D, P30D."""
    params = {"format": "json", "period": period, "parameterCd": "00060"}
    if site:
        params["sites"] = site
    elif state:
        params["stateCd"] = state
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://waterservices.usgs.gov/nwis/iv", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def drought(area_type: str = "state", area: str = "CA") -> dict:
    """US Drought Monitor. area_type: state/county/national."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://usdm.unl.edu/DmData/TimeSeries.aspx",
                        params={"area_type": area_type, "area": area, "format": "json"})
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
