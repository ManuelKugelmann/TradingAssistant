#!/bin/bash
# LibreChat Lite — install or update on Uberspace
# Called by bootstrap.sh or directly: bash setup.sh <app-dir> <version>
set -euo pipefail

# ── Load central config ──
for conf in "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/deploy.conf" \
            "$HOME/mcps/deploy.conf"; do
    [[ -f "$conf" ]] && { source "$conf"; break; }
done

SRC="${1:?Usage: setup.sh <app-dir> <version>}"
VER="${2:-unknown}"
APP="${APP_DIR:-$HOME/LibreChat}"
BAK="${APP}.prev"
DATA="${DATA_DIR:-$HOME/TradeAssistant_Data}"
STACK="${STACK_DIR:-$HOME/mcps}"
SVC="$HOME/etc/services.d/librechat.ini"
PORT="${LC_PORT:-3080}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
die()  { echo -e "${RED}✗${NC} $1" >&2; exit 1; }

# Dirs that survive updates
PERSIST=(uploads logs images)

# ── Pre-flight ──────────────────────────────
command -v node &>/dev/null || die "Node.js not found. Run: uberspace tools version use node ${NODE_VERSION:-22}"
NODE_MAJOR=$(node -v | cut -d. -f1 | tr -d 'v')
[[ "$NODE_MAJOR" -lt 20 ]] && die "Node.js ≥20 required (got $(node -v)). Run: uberspace tools version use node ${NODE_VERSION:-22}"

# ── Detect mode ─────────────────────────────
if [[ -d "$APP" ]]; then
    MODE="update"
    log "Updating to ${VER}..."
else
    MODE="install"
    log "Installing ${VER}..."
fi

# ── Stop service before swap ────────────────
if [[ "$MODE" == "update" ]]; then
    supervisorctl stop librechat 2>/dev/null || true
    sleep 2

    # Preserve .env and persistent dirs
    [[ -f "$APP/.env" ]] && cp "$APP/.env" "$SRC/.env"
    [[ -f "$APP/librechat.yaml" ]] && cp "$APP/librechat.yaml" "$SRC/librechat.yaml"
    for d in "${PERSIST[@]}"; do
        [[ -d "$APP/$d" ]] && { rm -rf "$SRC/$d"; mv "$APP/$d" "$SRC/$d"; }
    done
fi

# ── Atomic swap ─────────────────────────────
rm -rf "$BAK"
[[ -d "$APP" ]] && mv "$APP" "$BAK"
mv "$SRC" "$APP"

for d in "${PERSIST[@]}"; do mkdir -p "$APP/$d"; done

# ── Verify LibreChat app code is present ────
# The release bundle must include pre-built LibreChat (built in CI).
if [[ ! -f "$APP/api/server/index.js" ]]; then
    # Rollback: restore previous version if it existed
    rm -rf "$APP"
    [[ -d "$BAK" ]] && mv "$BAK" "$APP"
    die "LibreChat app code missing from bundle. Use a release built with CI (git tag + push)."
fi

# ── Copy default config if missing ──────────
if [[ ! -f "$APP/librechat.yaml" ]] && [[ -f "$APP/config/librechat.yaml" ]]; then
    cp "$APP/config/librechat.yaml" "$APP/librechat.yaml"
    # Replace __HOME__ placeholder with actual home directory
    sed -i "s|__HOME__|$HOME|g" "$APP/librechat.yaml"
    log "Copied default librechat.yaml (paths adjusted to $HOME)"
fi

# ── Data directory ──────────────────────────
mkdir -p "$DATA/files"
[[ ! -f "$DATA/.gitignore" ]] && cat > "$DATA/.gitignore" <<'GITIGNORE'
# Large binary uploads go here but don't sync
*.bin
*.zip
*.tar.gz
GITIGNORE

# ── Install MCP dependencies (skip if bundled by CI) ─
if [[ ! -d "$APP/node_modules/@modelcontextprotocol" ]]; then
    log "Installing MCP server packages..."
    cd "$APP"
    npm install --save \
        @modelcontextprotocol/server-filesystem \
        @modelcontextprotocol/server-memory \
        mcp-sqlite 2>/dev/null || warn "MCP package install had warnings (may be ok)"
    cd - >/dev/null
else
    log "MCP packages already bundled"
fi

# ── Install signals stack (Python MCP servers) ──
if [[ -d "$STACK/src" ]] && [[ ! -d "$STACK/venv" ]]; then
    log "Setting up signals stack Python environment..."
    cd "$STACK"
    python3 -m venv venv
    venv/bin/pip install -q -r requirements.txt
    cd - >/dev/null
    log "Signals stack ready"
elif [[ -d "$STACK/venv" ]]; then
    log "Signals stack already set up"
else
    warn "Signals stack not found at $STACK — trading MCPs won't be available"
    warn "Clone with: git clone https://github.com/${GH_USER:-ManuelKugelmann}/${GH_REPO_STACK:-TradingAssistant}.git $STACK"
fi

# ── First install ───────────────────────────
if [[ "$MODE" == "install" ]]; then
    # Generate .env from example
    if [[ ! -f "$APP/.env" ]]; then
        if [[ -f "$APP/config/.env.example" ]]; then
            cp "$APP/config/.env.example" "$APP/.env"
        elif [[ -f "$APP/.env.example" ]]; then
            cp "$APP/.env.example" "$APP/.env"
        else
            die ".env.example not found — cannot generate .env"
        fi
        # Generate crypto keys
        CREDS_KEY=$(openssl rand -hex 16)
        CREDS_IV=$(openssl rand -hex 8)
        JWT_SECRET=$(openssl rand -hex 32)
        JWT_REFRESH=$(openssl rand -hex 32)

        sed -i "s|^CREDS_KEY=.*|CREDS_KEY=$CREDS_KEY|" "$APP/.env"
        sed -i "s|^CREDS_IV=.*|CREDS_IV=$CREDS_IV|" "$APP/.env"
        sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" "$APP/.env"
        sed -i "s|^JWT_REFRESH_SECRET=.*|JWT_REFRESH_SECRET=$JWT_REFRESH|" "$APP/.env"

        # Disable search/meili
        if ! grep -q "^SEARCH=" "$APP/.env"; then
            echo "SEARCH=false" >> "$APP/.env"
        else
            sed -i "s|^SEARCH=.*|SEARCH=false|" "$APP/.env"
        fi

        log "Generated crypto keys in .env"
    fi

    # Supervisord service
    mkdir -p "$(dirname "$SVC")"
    cat > "$SVC" <<EOF
[program:librechat]
directory=${APP}
command=node --max-old-space-size=1024 api/server/index.js
environment=NODE_ENV=production
autostart=true
autorestart=true
startsecs=60
stopsignal=TERM
stopwaitsecs=10
EOF
    supervisorctl reread 2>/dev/null
    supervisorctl add librechat 2>/dev/null || true

    # Web backend
    uberspace web backend set / --http --port $PORT 2>/dev/null || true

    # Install ops shortcut
    mkdir -p "$HOME/bin"
    cp "$APP/scripts/TradeAssistant.sh" "$HOME/bin/ta" 2>/dev/null || true
    chmod +x "$HOME/bin/ta" 2>/dev/null || true
    ln -sf "$HOME/bin/ta" "$HOME/bin/TradeAssistant" 2>/dev/null || true

    echo ""
    log "Installed ${VER}"
    echo ""
    echo -e "${CYAN}📋 Next steps:${NC}"
    echo ""
    echo -e "  ${YELLOW}1.${NC} Configure LibreChat:"
    echo "     nano $APP/.env"
    echo ""
    echo "     Required:"
    echo "       MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/LibreChat"
    echo "       MONGO_URI_SIGNALS=mongodb+srv://user:pass@cluster.mongodb.net/signals"
    echo "       OPENAI_API_KEY=sk-...  and/or  ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
    echo -e "  ${YELLOW}2.${NC} Configure MCP servers (optional, defaults are fine):"
    echo "     nano $APP/librechat.yaml"
    echo ""
    echo -e "  ${YELLOW}3.${NC} Set up git-versioned data (optional):"
    echo "     bash $APP/scripts/setup-data-repo.sh ${GH_USER:-YOUR_USER}/${GH_REPO_DATA:-TradeAssistant_Data}"
    echo ""
    echo -e "  ${YELLOW}4.${NC} Start:"
    echo "     supervisorctl start librechat"
    echo ""
    echo -e "  ${YELLOW}5.${NC} Access:"
    echo "     https://${UBER_HOST:-$(hostname -f 2>/dev/null || echo 'YOUR_USER.uber.space')}"
    echo ""
else
    # ── Update: restart ─────────────────────
    supervisorctl start librechat 2>/dev/null || supervisorctl restart librechat 2>/dev/null || true
    log "Updated to ${VER} — service restarted"
fi

echo "$VER" > "$APP/.version"
