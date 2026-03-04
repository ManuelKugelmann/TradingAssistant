#!/bin/bash
# Set up git-versioned data directory for MCP file/memory/sqlite storage
# Usage: bash setup-data-repo.sh [YOUR_USER/TradeAssistant_Data]
set -euo pipefail

# ── Load central config ──
for conf in "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/deploy.conf" \
            "$HOME/mcps/deploy.conf"; do
    [[ -f "$conf" ]] && { source "$conf"; break; }
done

REPO="${1:-${GH_USER:-ManuelKugelmann}/${GH_REPO_DATA:-TradeAssistant_Data}}"
DATA="${DATA_DIR:-$HOME/TradeAssistant_Data}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
die()  { echo -e "${RED}✗${NC} $1" >&2; exit 1; }

# ── Check SSH key ───────────────────────────
if [[ ! -f "$HOME/.ssh/id_ed25519" ]] && [[ ! -f "$HOME/.ssh/id_rsa" ]]; then
    warn "No SSH key found. Generating one..."
    ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519"
    echo ""
    echo -e "${YELLOW}Add this public key to GitHub (Settings → SSH Keys):${NC}"
    echo ""
    cat "$HOME/.ssh/id_ed25519.pub"
    echo ""
    read -p "Press Enter after adding the key to GitHub..."
fi

# ── Init or clone ───────────────────────────
if [[ -d "$DATA/.git" ]]; then
    log "Data repo already initialized at $DATA"
else
    # Check if remote repo exists
    if git ls-remote "git@github.com:${REPO}.git" &>/dev/null; then
        log "Cloning existing data repo..."
        git clone "git@github.com:${REPO}.git" "$DATA.tmp"
        # Merge with existing data dir
        if [[ -d "$DATA" ]]; then
            cp -rn "$DATA"/* "$DATA.tmp/" 2>/dev/null || true
            rm -rf "$DATA"
        fi
        mv "$DATA.tmp" "$DATA"
    else
        warn "Remote repo not found. Create https://github.com/new → ${REPO} (private) first."
        echo "Then re-run this script."
        echo ""
        echo "Or init locally:"
        mkdir -p "$DATA"
        cd "$DATA"
        git init
        git remote add origin "git@github.com:${REPO}.git"
        log "Local repo initialized. Push after creating remote: cd $DATA && git push -u origin main"
        cd - >/dev/null
    fi
fi

# ── Ensure structure ────────────────────────
mkdir -p "$DATA/files"

if [[ ! -f "$DATA/.gitignore" ]]; then
    cat > "$DATA/.gitignore" <<'EOF'
# Skip large binaries
*.bin
*.zip
*.tar.gz
*.mp4
*.mp3

# OS junk
.DS_Store
Thumbs.db
EOF
    log "Created .gitignore"
fi

if [[ ! -f "$DATA/README.md" ]]; then
    cat > "$DATA/README.md" <<EOF
# TradeAssistant Data

Git-versioned data store for LibreChat MCP servers on ${UBER_HOST:-Uberspace}.

| Path | MCP Server | Content |
|---|---|---|
| \`files/\` | \`server-filesystem\` | User files, documents, exports |
| \`memory.jsonl\` | \`server-memory\` | Knowledge graph (entities + relations) |
| \`data.db\` | \`mcp-sqlite\` | Structured data (logs, research, notes) |

Auto-synced every 15 minutes via cron.
EOF
    log "Created README.md"
fi

# ── Initial commit ──────────────────────────
cd "$DATA"
git add -A
if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "init: data repo structure"
    git push -u origin main 2>/dev/null || warn "Push failed — create the remote repo first"
fi
cd - >/dev/null

# ── Cron for auto-sync ─────────────────────
CRON_CMD="cd $DATA && git add -A && git diff --cached --quiet || (git commit -m \"sync \$(date -Is)\" && git push) 2>&1 | logger -t ta-data-sync"

if crontab -l 2>/dev/null | grep -q "ta-data-sync"; then
    log "Cron sync already configured"
else
    (crontab -l 2>/dev/null; echo "*/15 * * * * $CRON_CMD") | crontab -
    log "Cron: syncing data to GitHub every 15 minutes"
fi

echo ""
log "Data repo ready at $DATA"
echo "  Files MCP:    $DATA/files/"
echo "  Memory MCP:   $DATA/memory.jsonl"
echo "  SQLite MCP:   $DATA/data.db"
echo "  Git remote:   git@github.com:${REPO}.git"
echo "  Auto-sync:    every 15 min via cron"
