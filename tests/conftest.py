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
        def __init__(self, name="", **kw):
            self.name = name
            self._tools = {}

        def tool(self, *a, **kw):
            """Decorator that registers and returns the function unchanged."""
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn
            return decorator

        def mount(self, child, namespace=""):
            """Collect tools from child with namespace prefix."""
            for name, fn in getattr(child, "_tools", {}).items():
                prefixed = f"{namespace}_{name}" if namespace else name
                self._tools[prefixed] = fn

        async def list_tools(self):
            """Return tool descriptors."""
            class _ToolInfo:
                def __init__(self, name):
                    self.name = name
            return [_ToolInfo(n) for n in sorted(self._tools)]

        def run(self, **kw):
            pass

    mock_fastmcp.FastMCP = _FakeMCP
    sys.modules["fastmcp"] = mock_fastmcp

    # Provide fastmcp.server.dependencies with a stub get_http_headers
    # so _get_user_id() / _get_user_key() can import it (raises RuntimeError
    # by default — same as when there's no active HTTP request).
    mock_server = MagicMock()
    mock_deps = MagicMock()

    def _stub_get_http_headers():
        raise RuntimeError("No active HTTP request (test stub)")

    mock_deps.get_http_headers = _stub_get_http_headers
    mock_server.dependencies = mock_deps
    mock_fastmcp.server = mock_server
    sys.modules["fastmcp.server"] = mock_server
    sys.modules["fastmcp.server.dependencies"] = mock_deps
