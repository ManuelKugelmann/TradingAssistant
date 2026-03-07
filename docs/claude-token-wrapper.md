# Claude Max Subscription via CLI Wrapper

Use your Claude Pro/Max subscription as a LibreChat endpoint — no API key billing.

---

## Architecture

```
LibreChat  ->  CLIProxyAPI (:8317)  ->  claude CLI (SDK)  ->  Anthropic
               OpenAI-compatible       CLAUDE_CODE_OAUTH_TOKEN
```

---

## Step 1 — Generate Long-Lived Token

Run on any machine with a browser (one-time):

```bash
claude setup-token
# -> sk-ant-oat01-...   <- shown ONCE, save it now
```

Store securely:

```bash
cat >> ~/.claude-auth.env << 'EOF'
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
EOF
chmod 600 ~/.claude-auth.env
```

Token is valid for **1 year**. No refresh cron needed.

---

## Step 2 — Install CLIProxyAPI

**macOS:**
```bash
brew install router-for-me/tap/cliproxyapi
```

**Linux / manual:**
```bash
# Requires Node 18+
npm install -g cliproxyapi
```

**On Uberspace (via ta):**
```bash
ta proxy setup
# Installs cliproxyapi, creates config, registers service
```

---

## Step 3 — Configure CLIProxyAPI

```bash
mkdir -p ~/.cli-proxy-api
cat > ~/.cli-proxy-api/config.yaml << 'EOF'
port: 8317
remote-management:
  allow-remote: false
  secret-key: ""
auth-dir: "~/.cli-proxy-api"
auth:
  providers: []    # empty = use OAuth token, not API key validation
debug: false
EOF
```

---

## Step 4 — Run the Proxy

```bash
source ~/.claude-auth.env
cliproxyapi --config ~/.cli-proxy-api/config.yaml
```

**Verify:**
```bash
curl http://localhost:8317/v1/models
# -> should list claude-sonnet-*, claude-opus-*, etc.
```

**As a systemd user service** (`~/.config/systemd/user/cliproxyapi.service`):
```ini
[Unit]
Description=CLIProxyAPI — Claude subscription OpenAI endpoint
After=network.target

[Service]
EnvironmentFile=%h/.claude-auth.env
ExecStart=cliproxyapi --config %h/.cli-proxy-api/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now cliproxyapi
```

**On Uberspace (supervisord):**
```bash
ta proxy start
# Uses ~/etc/services.d/cliproxyapi.ini
```

---

## Step 5 — Wire into LibreChat

Already preconfigured in `librechat.yaml` (commented out by default).

Uncomment the "Claude Max" endpoint section and restart:

```bash
ta yaml    # edit librechat.yaml
ta restart
```

Or manually add to `librechat.yaml`:

```yaml
endpoints:
  custom:
    - name: "Claude Max"
      apiKey: "dummy"
      baseURL: "http://localhost:8317/v1"
      models:
        default:
          - claude-sonnet-4-6
          - claude-opus-4-6
          - claude-haiku-4-5-20251001
        fetch: false
      titleConvo: true
      titleModel: "claude-sonnet-4-6"
      directEndpoint: true
      summarize: false
```

Ensure `.env` has `custom` in `ENDPOINTS`:
```bash
ENDPOINTS=openAI,anthropic,custom
```

Restart LibreChat — "Claude Max" appears in the model selector.

---

## Step 6 — Token Expiry Monitoring

Use `claude-auth-daemon.sh --once` in cron to check token health:

```bash
# crontab -e
*/30 * * * *  ~/bin/claude-auth-daemon.sh --once >> ~/.claude-auth.log 2>&1
# Annual renewal reminder
0 9 1 */11 * curl -sd "Claude setup-token renewal due -- $(hostname)" https://ntfy.sh/your-topic
```

On Uberspace, the `ta cron` hook runs the check automatically every 30 minutes
when `~/.claude-auth.env` exists.

---

## ta proxy Commands

```
ta proxy setup     Install CLIProxyAPI, create config, register service
ta proxy start     Start CLIProxyAPI service
ta proxy stop      Stop CLIProxyAPI service
ta proxy status    Show CLIProxyAPI service status
ta proxy test      Test proxy endpoint (curl /v1/models)
ta proxy token     Show token expiry info
```

---

## Limitations

| Feature | Status |
|---|---|
| Chat completions + streaming | Supported |
| Multi-turn conversation | Supported |
| Model selection | Supported |
| `temperature` / `top_p` / `max_tokens` | Ignored by CLI layer |
| 1M context window | Not available (OAuth restriction) |
| Token cost tracking in LibreChat | Not available (subscription, not per-token) |
| Multi-user LibreChat | Shared subscription limits apply |

---

## ToS Note

Anthropic's terms are designed for individual interactive use. Using a subscription
via CLI wrapper for **personal single-user** self-hosted LibreChat is a grey area at
moderate scale. For business/production use, the commercial API (`ANTHROPIC_API_KEY`)
is the correct path.
