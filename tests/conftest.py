"""Pytest conftest — mock heavy dependencies before store module imports them."""
import sys
from unittest.mock import MagicMock

# Mock pymongo (prevents cryptography/SSL import chain failure in sandbox)
if "pymongo" not in sys.modules:
    mock_pymongo = MagicMock()
    mock_pymongo.MongoClient = MagicMock
    sys.modules["pymongo"] = mock_pymongo

# Mock fastmcp (v3 API changes; we only need the @mcp.tool() decorator to be a no-op)
if "fastmcp" not in sys.modules:
    mock_fastmcp = MagicMock()

    class _FakeMCP:
        def __init__(self, *a, **kw):
            pass

        def tool(self, *a, **kw):
            """Decorator that returns the function unchanged."""
            def decorator(fn):
                return fn
            return decorator

        def run(self, **kw):
            pass

    mock_fastmcp.FastMCP = _FakeMCP
    sys.modules["fastmcp"] = mock_fastmcp
