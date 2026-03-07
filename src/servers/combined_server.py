"""Combined trading data server — all 12 domains in one process."""
from dotenv import load_dotenv
load_dotenv()

from fastmcp import FastMCP

mcp = FastMCP("trading-data",
    instructions="75+ data sources across 12 domains: weather, disaster, econ, "
                 "agri, conflict, commodity, health, politics, humanitarian, "
                 "transport, water, infra")

from weather_server import mcp as weather
from disasters_server import mcp as disaster
from macro_server import mcp as econ
from agri_server import mcp as agri
from conflict_server import mcp as conflict
from commodities_server import mcp as commodity
from health_server import mcp as health
from elections_server import mcp as politics
from humanitarian_server import mcp as humanitarian
from transport_server import mcp as transport
from water_server import mcp as water
from infra_server import mcp as infra

mcp.mount(weather, namespace="weather")
mcp.mount(disaster, namespace="disaster")
mcp.mount(econ, namespace="econ")
mcp.mount(agri, namespace="agri")
mcp.mount(conflict, namespace="conflict")
mcp.mount(commodity, namespace="commodity")
mcp.mount(health, namespace="health")
mcp.mount(politics, namespace="politics")
mcp.mount(humanitarian, namespace="humanitarian")
mcp.mount(transport, namespace="transport")
mcp.mount(water, namespace="water")
mcp.mount(infra, namespace="infra")

if __name__ == "__main__":
    mcp.run(transport="stdio")
