# CLAUDEUSMCP.md — Dev Workflow: Remote MCP Gateway on Uberspace

**This is a dev/ops workflow tool, NOT part of the production TradingAssistant stack.**

It deploys a lightweight MCP gateway on Uberspace so that Claude.ai (web + mobile)
and Claude Code can manage the server remotely. Think of it as SSH-over-MCP for our
dev workflow.

**Supported clients**: Claude.ai web, Claude iOS/Android, Claude Code CLI, Claude Desktop.

---

## Architecture

The gateway wraps `claude mcp serve` (Claude Code's built-in MCP server mode) behind
a FastMCP HTTP proxy with GitHub OAuth. Claude.ai gets direct access to Bash, Read,
Write, Edit, Grep, and all Claude Code tools — running natively on the Uberspace server.

**No custom Python tools needed.** Claude.ai can run `supervisorctl status`, `ta pull`,
read logs, edit configs — everything through Claude Code's native tools.

```
Claude.ai (web/mobile) / Claude Code CLI / Claude Desktop
    |
    |  1. Discovers OAuth via /.well-known/oauth-protected-resource
    |  2. Registers via DCR (/register) — gets back our GitHub app creds
    |  3. OAuth flow: user → our /authorize → GitHub login → our /auth/callback → client callback
    |  4. Streamable HTTP transport with JWT bearer token
    v
https://mcp.assist.uber.space/mcp
    |
    |  Uberspace nginx (auto TLS via Let's Encrypt)
    v
localhost:8070  (FastMCP HTTP proxy — ~50 lines of Python)
    |
    |  stdio proxy via create_proxy()
    v
claude mcp serve  (Claude Code as MCP server — NO API key needed)
    |
    +-- Bash          (shell commands: supervisorctl, ta, git, ...)
    +-- Read/Write    (file access: logs, profiles, configs, ...)
    +-- Edit          (in-place file editing)
    +-- GrepTool      (search across codebase)
    +-- GlobTool      (find files by pattern)
    +-- LS            (directory listing)
    +-- WebFetch      (fetch URLs)
    +-- Agent         (sub-agents for complex tasks)
```

### How `claude mcp serve` works

- Exposes Claude Code's **native tools only** as MCP tools over stdio
- Tools are direct execution — **no LLM calls**, no API key required
- Bash runs bash, Read reads files, Write writes files — zero overhead
- Claude.ai provides all the reasoning; the server just executes
- Does NOT proxy other configured MCP servers (only built-in tools)

### What this replaces

Previous plan had ~800 lines of custom Python tools. All unnecessary —
Claude Code's native tools cover every use case.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Uberspace account | `assist.uber.space` |
| Node.js 22+ | For Claude Code CLI (already on Uberspace) |
| Python 3.9+ | For FastMCP proxy (already on Uberspace) |
| Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| `fastmcp>=2.11` | For OAuth + proxy support |
| GitHub OAuth App | Created in Step 1 (free) |

**Not needed**: Anthropic API key (serve mode doesn't use LLM), custom Python tools,
`--dangerously-skip-permissions` (serve mode handles permissions via MCP protocol).

---

## Step 1: Create GitHub OAuth App

1. Go to https://github.com/settings/developers → **New OAuth App**
2. Fill in:
   - **Application name**: `TradingAssistant MCP Gateway`
   - **Homepage URL**: `https://mcp.assist.uber.space`
   - **Authorization callback URL**: `https://mcp.assist.uber.space/auth/callback`
3. Click **Register application**
4. Copy the **Client ID**
5. Click **Generate a new client secret**, copy it
6. Save both for Step 4

> **Important**: The callback URL points to **our server**, NOT to Claude.ai.
> FastMCP's OAuthProxy handles the full redirect chain:
>
> 1. Claude.ai registers via DCR → gets our GitHub app credentials
> 2. User clicks Connect → redirected to our `/authorize` endpoint
> 3. We redirect to GitHub login (callback = our `/auth/callback`)
> 4. GitHub redirects back to us with auth code
> 5. We exchange code for token, mint a FastMCP JWT
> 6. We redirect to Claude.ai's callback with our JWT
>
> This means all MCP clients (Claude.ai web, mobile, CLI, Desktop) work
> through the same OAuth App — no per-client callback URLs needed.

---

## Step 2: Set Up Subdomain on Uberspace

`.uber.space` subdomains need no DNS setup — Uberspace handles it automatically:

```bash
uberspace web domain add mcp.assist.uber.space
```

That's it. TLS certificate is provisioned automatically via Let's Encrypt.

---

## Step 3: Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
claude --version
```

### Verify serve mode works

```bash
echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  | claude mcp serve
# Should return JSON with server capabilities and tool list
```

---

## Step 4: Install Python Dependencies

```bash
cd ~/mcps
python3 -m venv venv 2>/dev/null || true
venv/bin/pip install -U 'fastmcp>=2.11' httpx python-dotenv
```

---

## Step 5: Create the Gateway

### `src/gateway/server.py`

```python
"""MCP Gateway — wraps `claude mcp serve` with GitHub OAuth + HTTP transport.

Bridges:  claude mcp serve (stdio) → FastMCP proxy (Streamable HTTP + OAuth)
Result:   Claude.ai gets direct Bash/Read/Write/Edit/Grep on the server.
"""
import os

import httpx
from dotenv import load_dotenv
from fastmcp.server import create_proxy
from fastmcp.server.auth.providers.github import GitHubProvider

load_dotenv()


def _get_auth():
    """GitHub OAuth via FastMCP's built-in GitHubProvider."""
    client_id = os.environ.get("GH_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GH_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        import warnings
        warnings.warn("No OAuth credentials — running WITHOUT auth", stacklevel=2)
        return None

    return GitHubProvider(
        client_id=client_id,
        client_secret=client_secret,
        base_url=os.environ.get(
            "GATEWAY_BASE_URL", "https://mcp.assist.uber.space"
        ),
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

### User access control

FastMCP's `GitHubProvider` handles OAuth but doesn't filter by GitHub username.
Two options for restricting access:

**Option A** — Rely on OAuth App privacy. Only people you explicitly share the
connection URL with can discover it. The OAuth App is yours, the URL is unlisted.
For a single-user dev tool, this is usually sufficient.

**Option B** — Add a custom token verifier that checks the GitHub username:

```python
# Add after GitHubProvider setup to restrict to specific users:
from fastmcp.server.auth import TokenVerifier

class GitHubUserFilter(TokenVerifier):
    def __init__(self, allowed_users: list[str]):
        self.allowed = {u.lower() for u in allowed_users}

    async def verify_token(self, token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            user = resp.json()
        if user["login"].lower() not in self.allowed:
            raise ValueError(f"User {user['login']} not in allowlist")
        return {"sub": user["login"], "name": user.get("name", "")}
```

Then pass `token_verifier=GitHubUserFilter(["ManuelKugelmann"])` to the provider.

### Create the files

```bash
mkdir -p ~/mcps/src/gateway
touch ~/mcps/src/gateway/__init__.py
# Copy server.py content above to ~/mcps/src/gateway/server.py
```

---

## Step 6: Configure Environment

```bash
cat >> ~/mcps/.env << 'EOF'

# ── MCP Gateway ──────────────────────────────
GH_OAUTH_CLIENT_ID=Iv1.xxxxxxxxxxxxxxxx
GH_OAUTH_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GATEWAY_PORT=8070
GATEWAY_BASE_URL=https://mcp.assist.uber.space
EOF
```

Replace the `GH_OAUTH_*` values with the ones from Step 1.

---

## Step 7: Register Supervisord Service

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

Route the subdomain to the gateway port:

```bash
uberspace web backend set mcp.assist.uber.space --http --port 8070
```

Verify:

```bash
supervisorctl status mcp-gateway
curl -s -o /dev/null -w "%{http_code}" https://mcp.assist.uber.space/mcp
# Expected: 401 (OAuth required) or 405 (method not allowed for GET)
```

---

## Step 9: Connect Clients

### Claude.ai (web)

1. Go to https://claude.ai → Settings → Connectors → **Add custom connector**
2. Enter URL: `https://mcp.assist.uber.space/mcp`
3. Click **Connect** → GitHub OAuth flow opens automatically
4. Authorize with your GitHub account
5. The connector appears as active — tools are now available in conversations

### Claude Mobile (iOS / Android)

Servers **cannot** be added directly from the mobile app. Add via claude.ai web first
(steps above), then:

1. Open Claude app on your phone
2. The connector syncs automatically from your account
3. Tools, prompts, and resources from the gateway are available in mobile conversations

### Claude Code CLI

```bash
claude mcp add trading-gateway --transport http https://mcp.assist.uber.space/mcp
claude mcp auth trading-gateway  # triggers OAuth flow in browser
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "trading-gateway": {
      "url": "https://mcp.assist.uber.space/mcp"
    }
  }
}
```

### Test it (any client)

> "Check the service status on the Uberspace server"

Claude uses the Bash tool to run `supervisorctl status` directly on the server.

---

## Step 10: Verify End-to-End

```bash
# Gateway running
supervisorctl status mcp-gateway

# HTTP endpoint responds
curl -s -o /dev/null -w "%{http_code}" https://mcp.assist.uber.space/mcp

# OAuth discovery works
curl -s https://mcp.assist.uber.space/.well-known/oauth-protected-resource

# Check logs
tail -5 ~/logs/mcp-gateway.out.log
tail -5 ~/logs/mcp-gateway.err.log
```

---

## What Claude.ai Can Do Through This Gateway

| Task | How |
|------|-----|
| Check service status | `Bash: supervisorctl status` |
| View logs | `Read: ~/logs/mcp-store.out.log` |
| Restart a service | `Bash: supervisorctl restart librechat` |
| Deploy update | `Bash: ~/bin/ta pull` |
| Edit configuration | `Edit: ~/mcps/.env` then `Bash: supervisorctl restart ...` |
| Search codebase | `GrepTool: pattern in ~/mcps/src/` |
| Browse profiles | `Read: ~/mcps/profiles/europe/countries/DEU.json` |
| Git operations | `Bash: cd ~/mcps && git log --oneline -10` |
| Debug a crash | Read logs → grep errors → inspect code → fix → restart |
| Disk usage | `Bash: df -h && du -sh ~/mcps ~/LibreChat ~/logs` |
| Check MongoDB | `Bash: ~/mcps/venv/bin/python -c "from pymongo import ..."` |

No custom tools. Claude.ai reasons about what to do, executes via native tools.

---

## Security Model

| Layer | Mechanism |
|-------|-----------|
| Authentication | GitHub OAuth 2.1 via FastMCP GitHubProvider + DCR |
| Token isolation | FastMCP issues its own JWTs — upstream GitHub tokens never exposed to clients |
| Authorization | OAuth App scope + optional user allowlist (see Step 5) |
| Transport | HTTPS only (Uberspace auto-TLS via Let's Encrypt) |
| Execution | Claude Code's built-in safety model |
| Origin | FastMCP validates Origin header per MCP spec |
| Consent | FastMCP shows consent screen before granting access |
| Client support | Web, iOS, Android, CLI, Desktop — all via same OAuth App |

---

## Updating

```bash
# Update gateway + stack code
ta pull && supervisorctl restart mcp-gateway

# Update Claude Code CLI
npm update -g @anthropic-ai/claude-code

# Update FastMCP
~/mcps/venv/bin/pip install -U 'fastmcp>=2.11'
```

---

## Troubleshooting

### Gateway won't start

```bash
tail -50 ~/logs/mcp-gateway.err.log
cd ~/mcps && venv/bin/python -m src.gateway.server  # run interactively
```

Common issues:
- `fastmcp` too old → `venv/bin/pip install -U 'fastmcp>=2.11'`
- `claude` not in PATH → `which claude` (npm global bin must be in PATH)
- Port conflict → `ss -tlnp | grep 8070`

### OAuth flow fails

1. Verify callback URL in GitHub OAuth App matches exactly:
   `https://mcp.assist.uber.space/auth/callback` (points to OUR server, not Claude.ai)
2. Check env vars: `grep GH_OAUTH ~/mcps/.env`
3. Test OAuth discovery: `curl -s https://mcp.assist.uber.space/.well-known/oauth-protected-resource`
4. Test DCR endpoint: `curl -s -X POST https://mcp.assist.uber.space/register -H 'Content-Type: application/json' -d '{"client_name":"test","redirect_uris":["http://localhost"]}'`

### Subdomain not resolving

```bash
uberspace web domain list  # verify mcp.assist.uber.space is listed
uberspace web backend list  # verify routing to port 8070
```

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
| `src/gateway/server.py` | FastMCP proxy (~50 lines) |
| `~/etc/services.d/mcp-gateway.ini` | Supervisord service config |

---

## References

- [Building custom connectors (Anthropic)](https://support.claude.com/en/articles/11503834-building-custom-connectors-via-remote-mcp-servers) — official guide for remote MCP + Claude.ai
- [About custom integrations (Anthropic)](https://support.anthropic.com/en/articles/11175166-about-custom-integrations-using-remote-mcp) — setup for Pro/Max/Team/Enterprise
- [FastMCP Proxy Servers](https://gofastmcp.com/servers/proxy) — `create_proxy()` docs
- [FastMCP OAuth Proxy](https://gofastmcp.com/servers/auth/oauth-proxy) — OAuthProxy / GitHubProvider / DCR flow
- [Uberspace Web Backends](https://manual.uberspace.de/web-backends/) — reverse proxy routing
- [Uberspace Domains](https://manual.uberspace.de/en/web-domains.html) — subdomain setup (`.uber.space` = no DNS needed)
- [claude mcp serve (#631)](https://github.com/anthropics/claude-code/issues/631) — serve mode discussion
- [claude-code-mcp (steipete)](https://github.com/steipete/claude-code-mcp) — Claude Code as MCP pattern
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) — official MCP guide
