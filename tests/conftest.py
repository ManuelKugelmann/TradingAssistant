"""Pytest conftest — mock heavy dependencies before store module imports them."""
import json
import sys
from unittest.mock import MagicMock

import pytest

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


@pytest.fixture
def mock_mongo():
    """Create a mock MongoDB client that returns mock collections."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_client.signals = mock_db
    mock_db.list_collection_names.return_value = []
    return mock_client, mock_db


@pytest.fixture
def mock_httpx_response():
    """Factory to create mock httpx responses."""
    def _make(json_data=None, status_code=200, text=""):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.text = text or json.dumps(json_data or {})
        resp.raise_for_status = MagicMock()
        if status_code >= 400:
            resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return resp
    return _make
