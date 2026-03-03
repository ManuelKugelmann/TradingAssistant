#!/bin/bash
# LibreChat ops shortcuts — usage: lc [command]
set -euo pipefail

# ── Load central config ──
STACK="${HOME}/mcps"
for conf in "$STACK/deploy.conf" \
            "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)/deploy.conf"; do
    [[ -f "$conf" ]] && { source "$conf"; break; }
done

APP="${APP_DIR:-$HOME/LibreChat}"
DATA="${DATA_DIR:-$HOME/librechat-data}"
STACK="${STACK_DIR:-$STACK}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

case "${1:-help}" in
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

        # Update lc shortcut
        cp "$STACK/librechat-uberspace/scripts/lc.sh" "$HOME/bin/lc" 2>/dev/null || true
        chmod +x "$HOME/bin/lc" 2>/dev/null || true

        # Update Python deps if changed
        "$STACK/venv/bin/pip" install -q -r "$STACK/requirements.txt" 2>/dev/null || true

        echo "$VER" > "$APP/.version"
        supervisorctl restart librechat 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Updated to ${VER} via git pull"
        ;;
    install)
        # Re-run the full installer (idempotent)
        bash "$STACK/install.sh"
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
        echo -e "${CYAN}LibreChat Lite — ops shortcuts${NC}"
        echo -e "${CYAN}Host: ${UBER_HOST:-$(hostname -f 2>/dev/null || echo 'unknown')}${NC}"
        echo ""
        echo "  lc s|status     Show service status + version"
        echo "  lc r|restart    Restart LibreChat"
        echo "  lc l|logs       Tail service logs"
        echo "  lc v|version    Show installed version"
        echo ""
        echo "  lc u|update     Update from latest GitHub release"
        echo "  lc pull         Quick update via git pull (dev)"
        echo "  lc install      Re-run full installer (idempotent)"
        echo "  lc rb|rollback  Rollback to previous version"
        echo ""
        echo "  lc sync         Force git sync of data dir"
        echo "  lc env          Edit .env"
        echo "  lc yaml         Edit librechat.yaml"
        echo "  lc conf         Edit deploy.conf"
        ;;
esac
