#!/usr/bin/env bats
# Uberspace-only tests — run on the deployed host via: ta check --test
#
# These tests require a live Uberspace environment:
#   - supervisord running
#   - LibreChat installed and configured
#   - Real services, ports, and filesystem
#
# Skipped automatically in CI and on non-Uberspace hosts.
# Can also run directly: bats tests/test_uberspace.bats

load helpers/setup

TA="$REPO_ROOT/librechat-uberspace/scripts/TradeAssistant.sh"

# ── Skip guard: only run on *.uber.space ──
setup() {
    if [[ "$(hostname -f 2>/dev/null)" != *".uber.space" ]]; then
        skip "Not on Uberspace host"
    fi
    # Use real HOME, not sandbox — we're testing the live system
    export STACK_DIR="${STACK_DIR:-$HOME/mcps}"
    export APP_DIR="${APP_DIR:-$HOME/LibreChat}"
    export DATA_DIR="${DATA_DIR:-$HOME/TradeAssistant_Data}"

    # Source deploy.conf if available
    [[ -f "$STACK_DIR/deploy.conf" ]] && source "$STACK_DIR/deploy.conf"
}

# No teardown_sandbox — we don't modify anything

# ══════════════════════════════════════════
#  Infrastructure
# ══════════════════════════════════════════

@test "uberspace: stack repo cloned" {
    [[ -d "$STACK_DIR/.git" ]]
}

@test "uberspace: deploy.conf exists" {
    [[ -f "$STACK_DIR/deploy.conf" ]]
}

@test "uberspace: Python venv exists" {
    [[ -x "$STACK_DIR/venv/bin/python" ]]
}

@test "uberspace: Python deps importable" {
    "$STACK_DIR/venv/bin/python" -c "import fastmcp, httpx, pymongo, dotenv"
}

@test "uberspace: Node.js >= 20" {
    NODE_VER="$(node -v)"
    NODE_MAJOR="${NODE_VER#v}"
    NODE_MAJOR="${NODE_MAJOR%%.*}"
    [[ "$NODE_MAJOR" -ge 20 ]]
}

@test "uberspace: ta shortcut installed" {
    [[ -x "$HOME/bin/ta" ]]
}

@test "uberspace: ta version returns something" {
    run "$HOME/bin/ta" version
    [[ "$status" -eq 0 ]]
    [[ -n "$output" ]]
}

# ══════════════════════════════════════════
#  LibreChat
# ══════════════════════════════════════════

@test "uberspace: LibreChat installed" {
    [[ -f "$APP_DIR/.version" ]]
}

@test "uberspace: LibreChat .env exists" {
    [[ -f "$APP_DIR/.env" ]]
}

@test "uberspace: LibreChat .env has MONGO_URI" {
    grep -q "^MONGO_URI=" "$APP_DIR/.env"
}

@test "uberspace: librechat.yaml exists with mcpServers" {
    [[ -f "$APP_DIR/librechat.yaml" ]]
    grep -q "mcpServers:" "$APP_DIR/librechat.yaml"
}

@test "uberspace: librechat.yaml has no __HOME__ placeholders" {
    ! grep -q "__HOME__" "$APP_DIR/librechat.yaml"
}

# ══════════════════════════════════════════
#  Services
# ══════════════════════════════════════════

@test "uberspace: supervisord is running" {
    supervisorctl status 2>/dev/null
}

@test "uberspace: librechat service registered" {
    run supervisorctl status librechat
    [[ "$status" -eq 0 ]]
}

@test "uberspace: librechat service is RUNNING" {
    run supervisorctl status librechat
    [[ "$output" == *"RUNNING"* ]]
}

@test "uberspace: LibreChat responds on HTTP" {
    LC_PORT="${LC_PORT:-3080}"
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${LC_PORT}/" 2>/dev/null)
    [[ "$HTTP_CODE" == "200" ]] || [[ "$HTTP_CODE" == "301" ]] || [[ "$HTTP_CODE" == "302" ]]
}

@test "uberspace: charts service responds" {
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8066/charts/" 2>/dev/null || echo "000")
    # Charts may return 404 (no chart requested) but should be reachable
    [[ "$HTTP_CODE" != "000" ]]
}

# ══════════════════════════════════════════
#  Data & Profiles
# ══════════════════════════════════════════

@test "uberspace: data directory exists" {
    [[ -d "$DATA_DIR" ]]
}

@test "uberspace: data directory is git-tracked" {
    [[ -d "$DATA_DIR/.git" ]]
}

@test "uberspace: profiles directory exists" {
    [[ -d "$STACK_DIR/profiles" ]]
}

@test "uberspace: at least one profile exists" {
    PROFILE_COUNT=$(find "$STACK_DIR/profiles" -name '*.json' -not -name 'INDEX_*' -not -path '*/SCHEMAS/*' | wc -l)
    [[ "$PROFILE_COUNT" -gt 0 ]]
}

# ══════════════════════════════════════════
#  Shell scripts
# ══════════════════════════════════════════

@test "uberspace: all scripts pass syntax check" {
    for script in "$STACK_DIR/librechat-uberspace/scripts/"*.sh; do
        run bash -n "$script"
        [[ "$status" -eq 0 ]] || {
            echo "Syntax error in: $(basename "$script")"
            return 1
        }
    done
}

# ══════════════════════════════════════════
#  Cron
# ══════════════════════════════════════════

@test "uberspace: ta cron is scheduled" {
    crontab -l 2>/dev/null | grep -q "ta cron"
}

# ══════════════════════════════════════════
#  CLIProxyAPI (optional — only if configured)
# ══════════════════════════════════════════

@test "uberspace: CLIProxyAPI responds (if configured)" {
    if [[ ! -f "$HOME/.claude-auth.env" ]] && [[ ! -f "$HOME/etc/services.d/cliproxyapi.ini" ]]; then
        skip "CLIProxyAPI not configured"
    fi
    PROXY_PORT="${CLIPROXY_PORT:-8317}"
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${PROXY_PORT}/v1/models" 2>/dev/null)
    [[ "$HTTP_CODE" == "200" ]]
}

@test "uberspace: Claude token file permissions are 600 (if exists)" {
    if [[ ! -f "$HOME/.claude-auth.env" ]]; then
        skip "No token file"
    fi
    PERMS=$(stat -c '%a' "$HOME/.claude-auth.env" 2>/dev/null || stat -f '%Lp' "$HOME/.claude-auth.env" 2>/dev/null)
    [[ "$PERMS" == "600" ]]
}

# ══════════════════════════════════════════
#  Web accessibility
# ══════════════════════════════════════════

@test "uberspace: public HTTPS responds" {
    UBER_HOST="${UBER_HOST:-$(hostname -f)}"
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://${UBER_HOST}/" 2>/dev/null || echo "000")
    [[ "$HTTP_CODE" == "200" ]] || [[ "$HTTP_CODE" == "301" ]] || [[ "$HTTP_CODE" == "302" ]]
}

# ══════════════════════════════════════════
#  MongoDB connectivity
# ══════════════════════════════════════════

@test "uberspace: signals store can reach MongoDB" {
    if ! grep -q "^MONGO_URI_SIGNALS=" "$STACK_DIR/.env" 2>/dev/null && \
       ! grep -q "^MONGO_URI_SIGNALS=" "$APP_DIR/.env" 2>/dev/null; then
        skip "MONGO_URI_SIGNALS not configured"
    fi
    run "$STACK_DIR/venv/bin/python" -c "
import os, sys
sys.path.insert(0, os.environ.get('STACK_DIR', os.path.expanduser('~/mcps')))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.environ.get('STACK_DIR', os.path.expanduser('~/mcps')), '.env'))
load_dotenv(os.path.join(os.environ.get('APP_DIR', os.path.expanduser('~/LibreChat')), '.env'))
uri = os.environ.get('MONGO_URI_SIGNALS', '')
if not uri:
    print('SKIP: no MONGO_URI_SIGNALS'); sys.exit(0)
from pymongo import MongoClient
client = MongoClient(uri, serverSelectionTimeoutMS=5000)
client.server_info()
print('MongoDB connected')
"
    [[ "$status" -eq 0 ]]
    [[ "$output" != *"error"* ]]
}

# ══════════════════════════════════════════
#  Domain server imports (catch missing deps)
# ══════════════════════════════════════════

@test "uberspace: domain servers are importable" {
    for server in "$STACK_DIR/src/servers/"*_server.py; do
        SERVER_NAME="$(basename "$server" .py)"
        run "$STACK_DIR/venv/bin/python" -c "
import sys, importlib.util
spec = importlib.util.spec_from_file_location('$SERVER_NAME', '$server')
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    print('OK: $SERVER_NAME')
except Exception as e:
    print(f'FAIL: $SERVER_NAME: {e}')
    sys.exit(1)
"
        [[ "$status" -eq 0 ]] || {
            echo "Import failed: $SERVER_NAME"
            echo "$output"
            return 1
        }
    done
}

@test "uberspace: signals store server importable" {
    run "$STACK_DIR/venv/bin/python" -c "
import sys, importlib.util
spec = importlib.util.spec_from_file_location('store', '$STACK_DIR/src/store/server.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('OK: signals store')
"
    [[ "$status" -eq 0 ]]
}

# ══════════════════════════════════════════
#  CLIProxyAPI setup-token (interactive)
# ══════════════════════════════════════════

@test "uberspace: claude CLI is installed (for setup-token)" {
    if ! command -v claude &>/dev/null; then
        skip "claude CLI not installed (npm i -g @anthropic-ai/claude-code)"
    fi
    run claude --version
    [[ "$status" -eq 0 ]]
}

@test "uberspace: CLIProxyAPI is installed" {
    if [[ ! -f "$HOME/etc/services.d/cliproxyapi.ini" ]]; then
        skip "CLIProxyAPI not configured"
    fi
    command -v cliproxyapi
}

@test "uberspace: CLIProxyAPI config is valid YAML" {
    if [[ ! -f "$HOME/.cli-proxy-api/config.yaml" ]]; then
        skip "No CLIProxyAPI config"
    fi
    # Basic validation: should have port key
    grep -q "port:" "$HOME/.cli-proxy-api/config.yaml"
}

@test "uberspace: ta check runs successfully" {
    run "$HOME/bin/ta" check
    # May have warnings but should produce output
    [[ "$output" == *"Health Check"* ]]
    [[ "$output" == *"Summary"* ]]
}

@test "uberspace: ta status runs" {
    run "$HOME/bin/ta" status
    [[ "$status" -eq 0 ]]
}

# ══════════════════════════════════════════
#  Web backend routing
# ══════════════════════════════════════════

@test "uberspace: web backend set for /" {
    run uberspace web backend list
    [[ "$output" == *"/"* ]]
}

@test "uberspace: web backend set for /charts" {
    run uberspace web backend list
    [[ "$output" == *"/charts"* ]]
}
