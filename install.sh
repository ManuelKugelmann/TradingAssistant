#!/bin/bash
# install.sh — One-liner full install/update for Uberspace
#
# Fresh install:
#   curl -sL https://raw.githubusercontent.com/ManuelKugelmann/TradingAssistant/main/install.sh | bash
#
# Or with a token for private repos:
#   curl -sL ... | GH_TOKEN=ghp_xxx bash
#
# Re-run safe: skips steps already done, preserves .env and config.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
die()  { echo -e "${RED}✗${NC} $1" >&2; exit 1; }

# ── Defaults (overridable via env) ──────────
GH_USER="${GH_USER:-ManuelKugelmann}"
GH_REPO="${GH_REPO:-TradingAssistant}"
STACK_DIR="${STACK_DIR:-$HOME/mcps}"
APP_DIR="${APP_DIR:-$HOME/LibreChat}"
DATA_DIR="${DATA_DIR:-$HOME/TradeAssistant_Data}"
LC_PORT="${LC_PORT:-3080}"
NODE_VERSION="${NODE_VERSION:-22}"
BRANCH="${BRANCH:-main}"

# Track whether .env files are new (need editing)
NEED_STACK_ENV=false
NEED_APP_ENV=false

echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo -e "${CYAN} TradingAssistant + LibreChat → Uberspace ${NC}"
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo ""

gh_curl() {
    local args=(-sf)
    [[ -n "${GH_TOKEN:-}" ]] && args+=(-H "Authorization: token $GH_TOKEN")
    curl "${args[@]}" "$@"
}

# ── 1. Node.js ──────────────────────────────
log "Setting Node.js ${NODE_VERSION}..."
uberspace tools version use node "$NODE_VERSION" 2>/dev/null || true
command -v node &>/dev/null || die "Node.js not available"
log "Node.js $(node -v)"

# ── 2. Clone or update repo ─────────────────
if [[ -d "$STACK_DIR/.git" ]]; then
    log "Repo exists at $STACK_DIR, pulling latest..."
    git -C "$STACK_DIR" pull --ff-only origin "$BRANCH" 2>/dev/null || \
        git -C "$STACK_DIR" fetch origin "$BRANCH" && \
        git -C "$STACK_DIR" reset --hard "origin/$BRANCH"
    log "Repo updated"
else
    log "Cloning repo..."
    if [[ -n "${GH_TOKEN:-}" ]]; then
        git clone -b "$BRANCH" "https://${GH_TOKEN}@github.com/${GH_USER}/${GH_REPO}.git" "$STACK_DIR"
    else
        git clone -b "$BRANCH" "https://github.com/${GH_USER}/${GH_REPO}.git" "$STACK_DIR"
    fi
    log "Cloned → $STACK_DIR"
fi

# ── Source central config now that it exists ─
[[ -f "$STACK_DIR/deploy.conf" ]] && source "$STACK_DIR/deploy.conf"

# ── 3. Python venv ──────────────────────────
if [[ -d "$STACK_DIR/venv" ]]; then
    log "Python venv exists, updating deps..."
    "$STACK_DIR/venv/bin/pip" install -q -r "$STACK_DIR/requirements.txt" 2>/dev/null || true
else
    log "Creating Python venv..."
    python3 -m venv "$STACK_DIR/venv"
    "$STACK_DIR/venv/bin/pip" install -q -r "$STACK_DIR/requirements.txt"
fi
log "Python venv ready"

# ── 4. Signals stack .env ───────────────────
if [[ ! -f "$STACK_DIR/.env" ]]; then
    cp "$STACK_DIR/.env.example" "$STACK_DIR/.env"
    NEED_STACK_ENV=true
    log "Created $STACK_DIR/.env (needs configuration)"
else
    log "Signals .env already exists"
fi

# ── 5. Register supervisord services ────────
log "Registering MCP services..."
mkdir -p ~/etc/services.d ~/logs

SERVERS=(agri disasters elections macro weather commodities conflict health humanitarian water transport infra)
for svc in "${SERVERS[@]}"; do
    cat > ~/etc/services.d/mcp-${svc}.ini << EOF
[program:mcp-${svc}]
directory=${STACK_DIR}
command=${STACK_DIR}/venv/bin/python src/servers/${svc}_server.py
autostart=false
autorestart=true
stderr_logfile=%(ENV_HOME)s/logs/mcp-${svc}.err.log
stdout_logfile=%(ENV_HOME)s/logs/mcp-${svc}.out.log
EOF
done

cat > ~/etc/services.d/mcp-store.ini << EOF
[program:mcp-store]
directory=${STACK_DIR}
command=${STACK_DIR}/venv/bin/python src/store/server.py
autostart=false
autorestart=true
stderr_logfile=%(ENV_HOME)s/logs/mcp-store.err.log
stdout_logfile=%(ENV_HOME)s/logs/mcp-store.out.log
EOF
log "MCP services registered"

# ── 6. LibreChat — try release bundle, fall back to local copy ──
NEED_LC_SETUP=false
APP="${APP_DIR:-$HOME/LibreChat}"

if [[ -d "$APP" ]] && [[ -f "$APP/.version" ]]; then
    log "LibreChat already installed ($(cat "$APP/.version"))"
else
    NEED_LC_SETUP=true
    NEED_APP_ENV=true
    TMP=$(mktemp -d)
    trap "rm -rf $TMP" EXIT

    # Try GitHub release first
    RELEASE_URL="https://api.github.com/repos/${GH_USER}/${GH_REPO}/releases/latest"
    if JSON=$(gh_curl "$RELEASE_URL" 2>/dev/null); then
        BUNDLE_URL=$(echo "$JSON" | grep -o '"browser_download_url":[^"]*"[^"]*librechat-bundle.tar.gz"' | cut -d'"' -f4)
        VER=$(echo "$JSON" | grep -o '"tag_name":[^"]*"[^"]*"' | cut -d'"' -f4)
    fi

    if [[ -n "${BUNDLE_URL:-}" ]]; then
        log "Downloading release ${VER}..."
        gh_curl -L -o "$TMP/bundle.tar.gz" "$BUNDLE_URL"
        mkdir -p "$TMP/app"
        tar xzf "$TMP/bundle.tar.gz" -C "$TMP/app"
        SRC="$TMP/app"
    else
        # No release — build from repo
        warn "No release found, installing from repo checkout..."
        VER="dev-$(git -C "$STACK_DIR" rev-parse --short HEAD)"
        SRC="$TMP/app"
        mkdir -p "$SRC/config" "$SRC/scripts"
        cp "$STACK_DIR/librechat-uberspace/config/librechat.yaml"  "$SRC/config/"
        cp "$STACK_DIR/librechat-uberspace/config/.env.example"    "$SRC/config/"
        cp "$STACK_DIR/librechat-uberspace/scripts/setup.sh"       "$SRC/scripts/"
        cp "$STACK_DIR/librechat-uberspace/scripts/bootstrap.sh"   "$SRC/scripts/"
        cp "$STACK_DIR/librechat-uberspace/scripts/TradeAssistant.sh" "$SRC/scripts/"
        cp "$STACK_DIR/librechat-uberspace/scripts/setup-data-repo.sh" "$SRC/scripts/"
    fi
fi

# ── 7. Run setup (handles install vs update, preserves .env) ──
if [[ "$NEED_LC_SETUP" == true ]]; then
    bash "$STACK_DIR/librechat-uberspace/scripts/setup.sh" "$SRC" "$VER"
else
    # Even on re-run, ensure supervisord + web backend are configured
    SVC="$HOME/etc/services.d/librechat.ini"
    if [[ ! -f "$SVC" ]]; then
        mkdir -p "$(dirname "$SVC")"
        cat > "$SVC" <<EOF
[program:librechat]
directory=${APP}
command=node --max-old-space-size=1024 api/server/index.js
environment=NODE_ENV=production
autostart=true
autorestart=true
startsecs=10
stopsignal=TERM
stopwaitsecs=10
EOF
        supervisorctl reread 2>/dev/null
        supervisorctl add librechat 2>/dev/null || true
        log "Supervisord service re-registered"
    fi
    uberspace web backend set / --http --port "${LC_PORT}" 2>/dev/null || true

    # Ensure ta shortcut exists
    mkdir -p "$HOME/bin"
    cp "$STACK_DIR/librechat-uberspace/scripts/TradeAssistant.sh" "$HOME/bin/ta" 2>/dev/null || true
    chmod +x "$HOME/bin/ta" 2>/dev/null || true
    ln -sf "$HOME/bin/ta" "$HOME/bin/TradeAssistant" 2>/dev/null || true
fi

# ── 8. Data directory ───────────────────────
mkdir -p "${DATA_DIR}/files"
log "Data dir ready at ${DATA_DIR}"

# ── 9. Reload supervisord ───────────────────
supervisorctl reread 2>/dev/null || true
supervisorctl update 2>/dev/null || true

# ── Done ────────────────────────────────────
UBER="${UBER_HOST:-$(hostname -f 2>/dev/null || echo "$USER.uber.space")}"
echo ""
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}✓${NC} Installation complete!"
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo ""

# ── Interactive config if .env files are new ─
if [[ "$NEED_STACK_ENV" == true ]] || [[ "$NEED_APP_ENV" == true ]]; then
    echo -e "${YELLOW}New .env files were created and need your API keys.${NC}"
    echo ""

    if [[ -t 0 ]]; then
        # Interactive terminal — offer to open nano
        if [[ "$NEED_STACK_ENV" == true ]]; then
            echo -e "${CYAN}[1/2]${NC} Signals stack config — set MONGO_URI_SIGNALS (optional API keys)"
            echo -e "      ${YELLOW}$STACK_DIR/.env${NC}"
            read -rp "      Open in nano now? [Y/n] " ans
            if [[ "${ans:-Y}" =~ ^[Yy]?$ ]]; then
                nano "$STACK_DIR/.env"
            fi
            echo ""
        fi

        if [[ "$NEED_APP_ENV" == true ]]; then
            echo -e "${CYAN}[2/2]${NC} LibreChat config — set MONGO_URI + LLM API key(s)"
            echo -e "      ${YELLOW}$APP/.env${NC}"
            read -rp "      Open in nano now? [Y/n] " ans
            if [[ "${ans:-Y}" =~ ^[Yy]?$ ]]; then
                nano "$APP/.env"
            fi
            echo ""
        fi
    else
        # Piped (curl|bash) — can't do interactive nano, print instructions
        echo -e "  ${CYAN}Step 1:${NC} Configure signals stack"
        echo "    nano $STACK_DIR/.env"
        echo "    # Set MONGO_URI_SIGNALS=mongodb+srv://... (optional API keys)"
        echo ""
        echo -e "  ${CYAN}Step 2:${NC} Configure LibreChat"
        echo "    nano $APP/.env"
        echo "    # Set MONGO_URI=mongodb+srv://..."
        echo "    # Set ANTHROPIC_API_KEY=sk-ant-...  and/or  OPENAI_API_KEY=sk-..."
        echo ""
    fi
fi

echo -e "  ${CYAN}Start:${NC}"
echo "    supervisorctl start librechat"
echo "    supervisorctl start mcp-store"
echo ""
echo -e "  ${CYAN}Access:${NC}"
echo "    https://${UBER}"
echo "    (first user to register becomes admin)"
echo ""
echo -e "  ${CYAN}Ops:${NC}"
echo "    ta help                    # all commands"
echo "    ta pull                    # quick git-pull update (dev)"
echo "    ta u                       # release update (prod)"
echo ""
