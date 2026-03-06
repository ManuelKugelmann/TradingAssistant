# CLAUDEUSMCP.md — Dev Workflow: Remote MCP Gateway on Uberspace

**This is a dev/ops workflow tool, NOT part of the production TradingAssistant stack.**

It deploys a lightweight MCP gateway on Uberspace so that Claude.ai and Claude Code (web)
can manage the server remotely. Think of it as SSH-over-MCP for our dev workflow.

---

## Architecture

The gateway wraps `claude mcp serve` (Claude Code's built-in MCP server mode) behind
a FastMCP HTTP proxy with OAuth. Claude.ai gets direct access to Bash, Read, Write,
Edit, Grep, and all Claude Code tools — running natively on the Uberspace server.

**No custom Python tools needed.** Claude.ai can just run `supervisorctl status`,
`ta pull`, read logs, edit configs — everything, through Claude Code's native tools.

```
Claude.ai / Claude Code (web)
    |
    |  HTTPS + OAuth 2.1
    |  Streamable HTTP transport
    v
https://mcp.assist.uber.space/mcp
    |
    |  Uberspace nginx reverse proxy (auto TLS)
    v
localhost:8070  (FastMCP HTTP proxy — ~30 lines of Python)
    |
    |  stdio proxy via create_proxy()
    v
claude mcp serve  (Claude Code as MCP server)
    |
    +-- Bash          (shell commands: supervisorctl, ta, git, ...)
    +-- Read/Write    (file access: logs, profiles, configs, ...)
    +-- Edit          (in-place file editing)
    +-- GrepTool      (search across codebase)
    +-- GlobTool      (find files)
    +-- LS            (directory listing)
    +-- dispatch_agent (sub-agents for complex tasks)
```

### Why this works

- `claude mcp serve` exposes Claude Code's tools as MCP tools over stdio
- The tools are direct execution — no extra LLM calls per tool invocation
- Claude.ai provides all the reasoning; the server just executes
- FastMCP `create_proxy()` bridges stdio -> HTTP and adds OAuth
- Total custom code: ~30 lines (proxy + auth config)

### What this replaces

The previous plan had ~800 lines of custom Python tools (ops.py, deploy.py,
diagnostics.py, data.py, config.py, shell.py, agent.py, security.py).
All unnecessary — Claude Code's native tools cover every use case.

---

## Prerequisites

- Uberspace account (e.g. `assist.uber.space`)
- Python 3.9+ and Node.js 22+ (both available on Uberspace)
- Anthropic Max subscription (or Team/Enterprise with headless access)
- A GitHub OAuth App (created in Step 1)

---

## Step 1: Create GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click **New OAuth App**
3. Fill in:
   - **Application name**: `TradingAssistant MCP Gateway`
   - **Homepage URL**: `https://mcp.assist.uber.space`
   - **Authorization callback URL**: `https://claude.ai/api/mcp/auth_callback`
4. Click **Register application**
5. Copy the **Client ID**
6. Click **Generate a new client secret**, copy it
7. Save both values for Step 4

> **For Claude Code CLI**: GitHub OAuth Apps only support one callback URL.
> For CLI testing, either create a second OAuth App or use `--header` bearer token.

---

## Step 2: Install Claude Code on Uberspace

```bash
# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Verify
claude --version
```

### Authenticate

```bash
# Auth with setup token (non-interactive, for headless/server use)
claude setup-token <your-token>

# Verify it works
claude --print "echo hello from Uberspace"

# Accept permissions for serve mode (one-time)
claude --dangerously-skip-permissions
# Then exit (Ctrl+C) — this just accepts the ToS
```

### Verify MCP serve mode

```bash
# Test that claude can serve as MCP (stdio)
echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | claude mcp serve
# Should return JSON with server capabilities
```

---

## Step 3: Install Python Dependencies

```bash
cd ~/mcps
python3 -m venv venv 2>/dev/null || true
venv/bin/pip install -q -r requirements.txt
```

> `requirements.txt` already includes `fastmcp>=2.11` (needed for OAuth + proxy).

---

## Step 4: Create the Gateway

The entire gateway is one small file:

### `src/gateway/server.py`

```python
"""MCP Gateway — wraps Claude Code's MCP serve mode with OAuth + HTTP transport.

Bridges:  claude mcp serve (stdio) -> FastMCP proxy (HTTP + OAuth)
Result:   Claude.ai gets direct Bash/Read/Write/Edit/Grep on the server.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from fastmcp.server import create_proxy
from fastmcp.server.auth import OAuthProxy


def _get_auth():
    """Configure GitHub OAuth, or None for local testing."""
    client_id = os.environ.get("GH_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GH_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        import warnings
        warnings.warn("No OAuth credentials — running WITHOUT auth", stacklevel=2)
        return None

    allowed = os.environ.get("GATEWAY_ALLOWED_USERS", "ManuelKugelmann")
    return OAuthProxy(
        client_id=client_id,
        client_secret=client_secret,
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        allowed_users=[u.strip() for u in allowed.split(",")],
        base_url=os.environ.get("GATEWAY_BASE_URL", "https://mcp.assist.uber.space"),
    )


# Wrap claude mcp serve (stdio) as an HTTP proxy with OAuth
proxy = create_proxy(
    "claude mcp serve",
    name="TradingAssistant Gateway",
    auth=_get_auth(),
)

if __name__ == "__main__":
    port = int(os.environ.get("GATEWAY_PORT", "8070"))
    proxy.run(transport="streamable-http", host="0.0.0.0", port=port)
```

That's the entire gateway. ~40 lines.

### Create the file

```bash
mkdir -p ~/mcps/src/gateway
cat > ~/mcps/src/gateway/__init__.py << 'EOF'
EOF

# Copy server.py from the repo (or create from the code block above)
```

---

## Step 5: Configure Environment

```bash
cat >> ~/mcps/.env << 'EOF'

# ── MCP Gateway ──────────────────────────────
GH_OAUTH_CLIENT_ID=Iv1.xxxxxxxxxxxxxxxx
GH_OAUTH_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GATEWAY_ALLOWED_USERS=ManuelKugelmann
GATEWAY_PORT=8070
GATEWAY_BASE_URL=https://mcp.assist.uber.space
EOF
```

Replace the `GH_OAUTH_*` values with the ones from Step 1.

---

## Step 6: Register Subdomain

```bash
# Add subdomain (Uberspace handles TLS automatically)
uberspace web domain add mcp.assist.uber.space
```

> **If subdomain fails** (DNS not configured), use path-based routing:
> ```bash
> uberspace web backend set /mcp-gateway --http --port 8070
> ```
> Update `GATEWAY_BASE_URL` accordingly.

### DNS Setup (if using subdomain)

Add a CNAME record:
```
mcp.assist.uber.space.  CNAME  assist.uber.space.
```

---

## Step 7: Create Supervisord Service

```bash
cat > ~/etc/services.d/mcp-gateway.ini << 'EOF'
[program:mcp-gateway]
directory=%(ENV_HOME)s/mcps
command=%(ENV_HOME)s/mcps/venv/bin/python -m src.gateway.server
autostart=true
autorestart=true
stderr_logfile=%(ENV_HOME)s/logs/mcp-gateway.err.log
stdout_logfile=%(ENV_HOME)s/logs/mcp-gateway.out.log
EOF

mkdir -p ~/logs
supervisorctl reread
supervisorctl add mcp-gateway
supervisorctl start mcp-gateway
```

---

## Step 8: Set Up Reverse Proxy

```bash
uberspace web backend set mcp.assist.uber.space --http --port 8070
```

Verify:

```bash
supervisorctl status mcp-gateway
curl -s https://mcp.assist.uber.space/mcp
```

---

## Step 9: Connect Claude.ai

1. Go to https://claude.ai
2. Settings -> Connectors -> **Add custom connector**
3. Enter URL: `https://mcp.assist.uber.space/mcp`
4. Click Connect — GitHub OAuth flow opens
5. Authorize with your GitHub account

### Test it

In a Claude.ai conversation:
> "Check the service status on the Uberspace server"

Claude.ai will use the Bash tool to run `supervisorctl status` directly on the server.

---

## Step 10: Connect Claude Code (CLI)

```bash
claude mcp add trading-gateway --transport http https://mcp.assist.uber.space/mcp
claude mcp auth trading-gateway
```

---

## Step 11: Verify End-to-End

```bash
# 1. Gateway is running
supervisorctl status mcp-gateway

# 2. HTTP endpoint responds
curl -s -o /dev/null -w "%{http_code}" https://mcp.assist.uber.space/mcp
# Expected: 401 (OAuth) or 200 (no auth)

# 3. OAuth discovery
curl -s https://mcp.assist.uber.space/.well-known/oauth-protected-resource

# 4. Logs
tail -5 ~/logs/mcp-gateway.out.log
tail -5 ~/logs/mcp-gateway.err.log
```

---

## What Claude.ai Can Do Through This Gateway

Once connected, Claude.ai has the same capabilities as running Claude Code locally
on the Uberspace server. Examples:

| Task | How Claude.ai does it |
|------|----------------------|
| Check service status | `Bash: supervisorctl status` |
| View logs | `Read: ~/logs/mcp-store.out.log` |
| Restart a service | `Bash: supervisorctl restart librechat` |
| Deploy update | `Bash: ~/bin/ta pull` |
| Edit configuration | `Edit: ~/mcps/.env` (then restart) |
| Search codebase | `GrepTool: pattern in ~/mcps/src/` |
| Browse profiles | `Read: ~/mcps/profiles/europe/countries/DEU.json` |
| Git operations | `Bash: cd ~/mcps && git log --oneline -10` |
| Debug a crash | Read logs, grep for errors, inspect code, fix + restart |
| MongoDB check | `Bash: ~/mcps/venv/bin/python -c "from pymongo import ..."` |
| Disk usage | `Bash: df -h && du -sh ~/mcps ~/LibreChat ~/logs` |

No custom tools needed. Claude.ai reasons about what to do, then executes via
Claude Code's native tools.

---

## Security Model

| Layer | Mechanism |
|-------|-----------|
| Authentication | GitHub OAuth 2.1 via FastMCP OAuthProxy |
| Authorization | User allowlist (`GATEWAY_ALLOWED_USERS`) |
| Transport | HTTPS only (Uberspace auto-TLS via Let's Encrypt) |
| Execution safety | Claude Code's built-in safety model (refuses destructive ops unless `--dangerously-skip-permissions`) |
| Origin validation | FastMCP validates Origin header per MCP spec |
| Process isolation | Each proxy session gets its own Claude Code backend |

### On `--dangerously-skip-permissions`

Claude Code's serve mode needs permissions accepted to function. This is a one-time
setup step. In normal operation, Claude Code still applies its safety model — it
won't `rm -rf /` or do destructive things without explicit instruction. The flag
just skips the interactive permission prompt that can't work in headless mode.

---

## Updating

```bash
# Update gateway + stack code
ta pull && supervisorctl restart mcp-gateway

# Update Claude Code CLI
npm update -g @anthropic-ai/claude-code
```

---

## Troubleshooting

### Gateway won't start

```bash
tail -50 ~/logs/mcp-gateway.err.log
cd ~/mcps && venv/bin/python -m src.gateway.server
```

Common issues:
- `fastmcp` too old: `venv/bin/pip install -U 'fastmcp>=2.11'`
- `claude` not in PATH: `which claude` (ensure npm global bin is in PATH)
- Port conflict: `ss -tlnp | grep 8070`

### OAuth flow fails

1. Verify callback URL in GitHub OAuth App: `https://claude.ai/api/mcp/auth_callback`
2. Check `GH_OAUTH_CLIENT_ID` / `GH_OAUTH_CLIENT_SECRET` in `~/mcps/.env`
3. Test: `curl https://mcp.assist.uber.space/.well-known/oauth-protected-resource`

### Claude Code auth expired

```bash
claude setup-token <new-token>
supervisorctl restart mcp-gateway
```

### `.well-known` not found

Use a subdomain (not path-based routing) so FastMCP serves well-known at the domain root.

---

## Uninstall

```bash
supervisorctl stop mcp-gateway
rm ~/etc/services.d/mcp-gateway.ini
supervisorctl reread
uberspace web backend del mcp.assist.uber.space
uberspace web domain del mcp.assist.uber.space
rm -rf ~/mcps/src/gateway
```

---

## Files

| File | Purpose |
|------|---------|
| `src/gateway/__init__.py` | Package marker |
| `src/gateway/server.py` | FastMCP proxy (~40 lines) |
| `~/etc/services.d/mcp-gateway.ini` | Supervisord service |

---

## References

- [FastMCP Proxy Servers](https://gofastmcp.com/servers/proxy) — `create_proxy()` docs
- [claude-code-mcp (steipete)](https://github.com/steipete/claude-code-mcp) — Claude Code as MCP server pattern
- [claude mcp serve issue #631](https://github.com/anthropics/claude-code/issues/631) — MCP serve mode discussion
- [FastMCP Remote OAuth](https://gofastmcp.com/servers/auth/remote-oauth) — OAuthProxy docs
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) — official MCP integration guide
