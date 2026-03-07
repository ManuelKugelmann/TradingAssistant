"""Combined trading server — signals store + 12 data domains in one process."""
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Allow importing store/server.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "store"))

from fastmcp import FastMCP

mcp = FastMCP("trading",
    instructions="Trading signals: store (profiles, snapshots, notes, risk gate) + 12 OSINT data domains (75+ sources)")

# Signals store (profiles, snapshots, charts, archival)
from server import mcp as store

# 12 data domains
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

mcp.mount(store, namespace="store")
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
    import os
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        port = int(os.environ.get("MCP_PORT", "8071"))
        mcp.run(transport="streamable-http", host="127.0.0.1", port=port,
                stateless_http=True)
    else:
        mcp.run(transport="stdio")
