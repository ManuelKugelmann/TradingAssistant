#!/bin/bash
# TradeAssistant ops — single entry point for install + daily ops
#
# Fresh install (one-liner):
#   curl -sL https://raw.githubusercontent.com/ManuelKugelmann/TradingAssistant/main/librechat-uberspace/scripts/TradeAssistant.sh | bash
#   # or with token: curl -sL ... | GH_TOKEN=ghp_xxx bash
#
# After install:
#   ta help              # show all commands
#   ta install           # re-run full installer (idempotent)
#
# Installed as ~/bin/ta (shorthand) and ~/bin/TradeAssistant
set -euo pipefail

# ── Defaults (work before repo/config exist) ──
GH_USER="${GH_USER:-ManuelKugelmann}"
GH_REPO="${GH_REPO:-TradingAssistant}"
STACK_DIR="${STACK_DIR:-$HOME/mcps}"
APP_DIR="${APP_DIR:-$HOME/LibreChat}"
DATA_DIR="${DATA_DIR:-$HOME/TradeAssistant_Data}"
LC_PORT="${LC_PORT:-3080}"
NODE_VERSION="${NODE_VERSION:-22}"
BRANCH="${BRANCH:-main}"

# ── Load central config if available ──
for _conf in "$STACK_DIR/deploy.conf" \
             "$(cd "$(dirname "${BASH_SOURCE[0]:-/dev/null}")/../.." 2>/dev/null && pwd)/deploy.conf" 2>/dev/null; do
    [[ -f "$_conf" ]] && { source "$_conf"; break; }
done
unset _conf

APP="${APP_DIR:-$HOME/LibreChat}"
DATA="${DATA_DIR:-$HOME/TradeAssistant_Data}"
STACK="${STACK_DIR:-$HOME/mcps}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
die()  { echo -e "${RED}✗${NC} $1" >&2; exit 1; }

# ── Auto-detect: piped with no args → install ──
CMD="${1:-help}"
if [[ "$CMD" == "help" ]] && ! [[ -d "$STACK/.git" ]]; then
    CMD="install"
fi

# ═══════════════════════════════════════════════
#  install — full install/update (idempotent)
# ═══════════════════════════════════════════════
_do_install() {
    # Track whether .env files are new (need editing)
    local NEED_STACK_ENV=false
    local NEED_APP_ENV=false

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
    if [[ -d "$STACK/.git" ]]; then
        log "Repo exists at $STACK, pulling latest..."
        git -C "$STACK" pull --ff-only origin "$BRANCH" 2>/dev/null || \
            git -C "$STACK" fetch origin "$BRANCH" && \
            git -C "$STACK" reset --hard "origin/$BRANCH"
        log "Repo updated"
    else
        log "Cloning repo..."
        if [[ -n "${GH_TOKEN:-}" ]]; then
            git clone -b "$BRANCH" "https://${GH_TOKEN}@github.com/${GH_USER}/${GH_REPO}.git" "$STACK"
        else
            git clone -b "$BRANCH" "https://github.com/${GH_USER}/${GH_REPO}.git" "$STACK"
        fi
        log "Cloned → $STACK"
    fi

    # ── Source central config now that it exists ─
    [[ -f "$STACK/deploy.conf" ]] && source "$STACK/deploy.conf"

    # ── 3. Python venv ──────────────────────────
    if [[ -d "$STACK/venv" ]]; then
        log "Python venv exists, updating deps..."
        "$STACK/venv/bin/pip" install -q -r "$STACK/requirements.txt" 2>/dev/null || true
    else
        log "Creating Python venv..."
        python3 -m venv "$STACK/venv"
        "$STACK/venv/bin/pip" install -q -r "$STACK/requirements.txt"
    fi
    log "Python venv ready"

    # ── 4. Signals stack .env ───────────────────
    if [[ ! -f "$STACK/.env" ]]; then
        cp "$STACK/.env.example" "$STACK/.env"
        NEED_STACK_ENV=true
        log "Created $STACK/.env (needs configuration)"
    else
        log "Signals .env already exists"
    fi

    # ── 5. Register supervisord services ────────
    log "Registering MCP services..."
    mkdir -p ~/etc/services.d ~/logs

    local SERVERS=(agri disasters elections macro weather commodities conflict health humanitarian water transport infra)
    for svc in "${SERVERS[@]}"; do
        cat > ~/etc/services.d/mcp-${svc}.ini << SVCEOF
[program:mcp-${svc}]
directory=${STACK}
command=${STACK}/venv/bin/python src/servers/${svc}_server.py
autostart=false
autorestart=true
stderr_logfile=%(ENV_HOME)s/logs/mcp-${svc}.err.log
stdout_logfile=%(ENV_HOME)s/logs/mcp-${svc}.out.log
SVCEOF
    done

    cat > ~/etc/services.d/mcp-store.ini << SVCEOF
[program:mcp-store]
directory=${STACK}
command=${STACK}/venv/bin/python src/store/server.py
autostart=false
autorestart=true
stderr_logfile=%(ENV_HOME)s/logs/mcp-store.err.log
stdout_logfile=%(ENV_HOME)s/logs/mcp-store.out.log
SVCEOF
    log "MCP services registered"

    # ── 6. LibreChat — try release bundle, fall back to local copy ──
    local NEED_LC_SETUP=false

    if [[ -d "$APP" ]] && [[ -f "$APP/.version" ]]; then
        log "LibreChat already installed ($(cat "$APP/.version"))"
    else
        NEED_LC_SETUP=true
        NEED_APP_ENV=true
        local TMP
        TMP=$(mktemp -d)
        trap "rm -rf $TMP" EXIT

        # Try GitHub release first
        local RELEASE_URL="https://api.github.com/repos/${GH_USER}/${GH_REPO}/releases/latest"
        local JSON="" BUNDLE_URL="" VER=""
        if JSON=$(gh_curl "$RELEASE_URL" 2>/dev/null); then
            BUNDLE_URL=$(echo "$JSON" | grep -o '"browser_download_url":[^"]*"[^"]*librechat-bundle.tar.gz"' | cut -d'"' -f4)
            VER=$(echo "$JSON" | grep -o '"tag_name":[^"]*"[^"]*"' | cut -d'"' -f4)
        fi

        local SRC=""
        if [[ -n "${BUNDLE_URL:-}" ]]; then
            log "Downloading release ${VER}..."
            gh_curl -L -o "$TMP/bundle.tar.gz" "$BUNDLE_URL"
            mkdir -p "$TMP/app"
            tar xzf "$TMP/bundle.tar.gz" -C "$TMP/app"
            SRC="$TMP/app"
        else
            # No release — build from repo
            warn "No release found, installing from repo checkout..."
            VER="dev-$(git -C "$STACK" rev-parse --short HEAD)"
            SRC="$TMP/app"
            mkdir -p "$SRC/config" "$SRC/scripts"
            cp "$STACK/librechat-uberspace/config/librechat.yaml"        "$SRC/config/"
            cp "$STACK/librechat-uberspace/config/.env.example"          "$SRC/config/"
            cp "$STACK/librechat-uberspace/scripts/setup.sh"             "$SRC/scripts/"
            cp "$STACK/librechat-uberspace/scripts/bootstrap.sh"         "$SRC/scripts/"
            cp "$STACK/librechat-uberspace/scripts/TradeAssistant.sh"    "$SRC/scripts/"
            cp "$STACK/librechat-uberspace/scripts/setup-data-repo.sh"   "$SRC/scripts/"
        fi

        # ── 7. Run setup (handles install vs update, preserves .env) ──
        bash "$STACK/librechat-uberspace/scripts/setup.sh" "$SRC" "$VER"
    fi

    if [[ "$NEED_LC_SETUP" == false ]]; then
        # Even on re-run, ensure supervisord + web backend are configured
        local SVC="$HOME/etc/services.d/librechat.ini"
        if [[ ! -f "$SVC" ]]; then
            mkdir -p "$(dirname "$SVC")"
            cat > "$SVC" <<SVCEOF
[program:librechat]
directory=${APP}
command=node --max-old-space-size=1024 api/server/index.js
environment=NODE_ENV=production
autostart=true
autorestart=true
startsecs=10
stopsignal=TERM
stopwaitsecs=10
SVCEOF
            supervisorctl reread 2>/dev/null
            supervisorctl add librechat 2>/dev/null || true
            log "Supervisord service re-registered"
        fi
        uberspace web backend set / --http --port "${LC_PORT}" 2>/dev/null || true
    fi

    # ── 8. Install ta shortcut ──────────────────
    mkdir -p "$HOME/bin"
    cp "$STACK/librechat-uberspace/scripts/TradeAssistant.sh" "$HOME/bin/ta" 2>/dev/null || true
    chmod +x "$HOME/bin/ta" 2>/dev/null || true
    ln -sf "$HOME/bin/ta" "$HOME/bin/TradeAssistant" 2>/dev/null || true

    # ── 9. Data directory ───────────────────────
    mkdir -p "${DATA}/files"
    log "Data dir ready at ${DATA}"

    # ── 10. Reload supervisord ──────────────────
    supervisorctl reread 2>/dev/null || true
    supervisorctl update 2>/dev/null || true

    # ── Done ────────────────────────────────────
    local UBER="${UBER_HOST:-$(hostname -f 2>/dev/null || echo "$USER.uber.space")}"
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
                echo -e "      ${YELLOW}$STACK/.env${NC}"
                read -rp "      Open in nano now? [Y/n] " ans
                if [[ "${ans:-Y}" =~ ^[Yy]?$ ]]; then
                    nano "$STACK/.env"
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
            echo "    nano $STACK/.env"
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
}

# ═══════════════════════════════════════════════
#  Command dispatch
# ═══════════════════════════════════════════════
case "$CMD" in
    s|status)
        supervisorctl status librechat 2>/dev/null || echo "librechat: not registered"
        supervisorctl status mcp-store 2>/dev/null || true
        echo -e "${CYAN}Version:${NC} $(cat "$APP/.version" 2>/dev/null || echo 'unknown')"
        echo -e "${CYAN}Host:${NC} ${UBER_HOST:-$(hostname -f 2>/dev/null || echo 'unknown')}"
        ;;
    r|restart)
        supervisorctl restart librechat
        echo -e "${GREEN}✓${NC} Restarted"
        ;;
    l|logs)
        supervisorctl tail -f librechat
        ;;
    v|version)
        cat "$APP/.version" 2>/dev/null || echo "unknown"
        ;;
    u|update)
        echo -e "${CYAN}Pulling latest release...${NC}"
        bash "$STACK/librechat-uberspace/scripts/bootstrap.sh"
        ;;
    pull)
        # Quick dev update — git pull the stack repo, re-copy configs, restart
        echo -e "${CYAN}Dev update via git pull...${NC}"
        git -C "$STACK" pull --ff-only
        VER="dev-$(git -C "$STACK" rev-parse --short HEAD)"

        # Re-copy scripts and config
        mkdir -p "$APP/scripts" "$APP/config"
        cp "$STACK/librechat-uberspace/scripts/"*.sh "$APP/scripts/" 2>/dev/null || true
        if [[ -f "$STACK/librechat-uberspace/config/librechat.yaml" ]] && [[ ! -f "$APP/librechat.yaml" ]]; then
            cp "$STACK/librechat-uberspace/config/librechat.yaml" "$APP/librechat.yaml"
            sed -i "s|__HOME__|$HOME|g" "$APP/librechat.yaml"
        fi

        # Update ta/TradeAssistant shortcuts
        cp "$STACK/librechat-uberspace/scripts/TradeAssistant.sh" "$HOME/bin/ta" 2>/dev/null || true
        chmod +x "$HOME/bin/ta" 2>/dev/null || true
        ln -sf "$HOME/bin/ta" "$HOME/bin/TradeAssistant" 2>/dev/null || true

        # Update Python deps if changed
        "$STACK/venv/bin/pip" install -q -r "$STACK/requirements.txt" 2>/dev/null || true

        echo "$VER" > "$APP/.version"
        supervisorctl restart librechat 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Updated to ${VER} via git pull"
        ;;
    install)
        _do_install
        ;;
    rb|rollback)
        if [[ ! -d "${APP}.prev" ]]; then
            echo -e "${RED}✗${NC} No previous version to rollback to"
            exit 1
        fi
        supervisorctl stop librechat
        rm -rf "$APP"
        mv "${APP}.prev" "$APP"
        supervisorctl start librechat
        echo -e "${GREEN}✓${NC} Rolled back to $(cat "$APP/.version" 2>/dev/null || echo 'unknown')"
        ;;
    sync)
        if [[ -d "$DATA/.git" ]]; then
            cd "$DATA"
            git add -A
            if ! git diff --cached --quiet; then
                git commit -m "sync $(date -Is)"
                git push
                echo -e "${GREEN}✓${NC} Data synced to GitHub"
            else
                echo -e "${YELLOW}⚠${NC} No changes to sync"
            fi
        else
            echo -e "${RED}✗${NC} Data repo not initialized. Run: bash $APP/scripts/setup-data-repo.sh"
        fi
        ;;
    env)
        ${EDITOR:-nano} "$APP/.env"
        ;;
    yaml)
        ${EDITOR:-nano} "$APP/librechat.yaml"
        ;;
    conf)
        ${EDITOR:-nano} "$STACK/deploy.conf"
        ;;
    *)
        echo -e "${CYAN}TradeAssistant — ops shortcuts${NC}"
        echo -e "${CYAN}Host: ${UBER_HOST:-$(hostname -f 2>/dev/null || echo 'unknown')}${NC}"
        echo ""
        echo "  ta s|status     Show service status + version"
        echo "  ta r|restart    Restart LibreChat"
        echo "  ta l|logs       Tail service logs"
        echo "  ta v|version    Show installed version"
        echo ""
        echo "  ta u|update     Update from latest GitHub release"
        echo "  ta pull         Quick update via git pull (dev)"
        echo "  ta install      Re-run full installer (idempotent)"
        echo "  ta rb|rollback  Rollback to previous version"
        echo ""
        echo "  ta sync         Force git sync of data dir"
        echo "  ta env          Edit .env"
        echo "  ta yaml         Edit librechat.yaml"
        echo "  ta conf         Edit deploy.conf"
        echo ""
        echo "  Fresh install:"
        echo "    curl -sL https://raw.githubusercontent.com/${GH_USER}/${GH_REPO}/main/librechat-uberspace/scripts/TradeAssistant.sh | bash"
        ;;
esac
