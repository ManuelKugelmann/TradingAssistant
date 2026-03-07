"""Combined trading server — signals store + 9 data domains in one process."""
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Allow importing store/server.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "store"))

from fastmcp import FastMCP

mcp = FastMCP("trading",
    instructions="Trading signals: store (profiles, snapshots, notes, risk gate) + 9 OSINT data domains (75+ sources)")

# Signals store (profiles, snapshots, charts, archival)
from server import mcp as store

# 9 data domains (weather+water, disaster, econ, agri, conflict+humanitarian,
#                  commodity, health, politics, transport+infra)
from weather_server import mcp as weather
from disasters_server import mcp as disaster
from macro_server import mcp as econ
from agri_server import mcp as agri
from conflict_server import mcp as conflict
from commodities_server import mcp as commodity
from health_server import mcp as health
from elections_server import mcp as politics
from transport_server import mcp as transport

mcp.mount(store, namespace="store")
mcp.mount(weather, namespace="weather")
mcp.mount(disaster, namespace="disaster")
mcp.mount(econ, namespace="econ")
mcp.mount(agri, namespace="agri")
mcp.mount(conflict, namespace="conflict")
mcp.mount(commodity, namespace="commodity")
mcp.mount(health, namespace="health")
mcp.mount(politics, namespace="politics")
mcp.mount(transport, namespace="transport")

if __name__ == "__main__":
    import os
    transport_mode = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport_mode == "streamable-http":
        port = int(os.environ.get("MCP_PORT", "8071"))
        mcp.run(transport="streamable-http", host="127.0.0.1", port=port,
                stateless_http=True)
    else:
        mcp.run(transport="stdio")
