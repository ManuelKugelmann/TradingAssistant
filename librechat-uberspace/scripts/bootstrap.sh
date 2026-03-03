#!/bin/bash
# LibreChat Lite bootstrap — curl | bash to install or update
set -euo pipefail

# ── Load central config ──
for conf in "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/deploy.conf" \
            "$HOME/mcps/deploy.conf"; do
    [[ -f "$conf" ]] && { source "$conf"; break; }
done

REPO="${LIBRECHAT_REPO:-${GH_USER:-ManuelKugelmann}/${GH_REPO_STACK:-TradingAssistant}}"
API="https://api.github.com/repos/${REPO}/releases/latest"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
die()  { echo -e "${RED}✗${NC} $1" >&2; exit 1; }

gh_curl() {
    if [[ -n "${GH_TOKEN:-}" ]]; then
        curl -sf -H "Authorization: token $GH_TOKEN" "$@"
    else
        curl -sf "$@"
    fi
}

echo -e "${CYAN}═══════════════════════════════════════${NC}"
echo -e "${CYAN} LibreChat Lite → ${UBER_HOST:-Uberspace}${NC}"
echo -e "${CYAN}═══════════════════════════════════════${NC}"
echo ""

log "Fetching latest release from ${REPO}..."
JSON=$(gh_curl "$API") || die "Failed to fetch release info. For private repos: export GH_TOKEN=ghp_xxx"

URL=$(echo "$JSON" | grep -o '"browser_download_url":[^"]*"[^"]*librechat-bundle.tar.gz"' | cut -d'"' -f4)
VER=$(echo "$JSON" | grep -o '"tag_name":[^"]*"[^"]*"' | cut -d'"' -f4)
[[ -z "$URL" ]] && die "No bundle found in release"

TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT

log "Downloading ${VER}..."
gh_curl -L -o "$TMP/bundle.tar.gz" "$URL"

log "Extracting..."
mkdir -p "$TMP/app"
tar xzf "$TMP/bundle.tar.gz" -C "$TMP/app"

exec bash "$TMP/app/scripts/setup.sh" "$TMP/app" "$VER"
