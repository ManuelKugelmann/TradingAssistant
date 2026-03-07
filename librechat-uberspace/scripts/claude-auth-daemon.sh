#!/bin/bash
# claude-auth-daemon.sh — Monitor Claude OAuth token health
#
# Usage:
#   claude-auth-daemon.sh --once     # single check (for cron)
#   claude-auth-daemon.sh            # continuous loop (every 30 min)
#
# Requires: CLAUDE_CODE_OAUTH_TOKEN set in environment or ~/.claude-auth.env
set -euo pipefail

AUTH_ENV="${HOME}/.claude-auth.env"
PROXY_URL="${CLIPROXY_URL:-http://localhost:8317}"
LOG_TAG="claude-auth"

# ── Load token ──
if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]] && [[ -f "$AUTH_ENV" ]]; then
    # shellcheck source=/dev/null
    source "$AUTH_ENV"
fi

if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
    echo "[$LOG_TAG] ERROR: CLAUDE_CODE_OAUTH_TOKEN not set"
    echo "[$LOG_TAG] Run: claude setup-token"
    exit 1
fi

_check() {
    local http_code
    http_code=$(curl -s -o /dev/null -w '%{http_code}' \
        "${PROXY_URL}/v1/models" 2>/dev/null || echo "000")

    case "$http_code" in
        200)
            echo "[$LOG_TAG] $(date -Is) OK — proxy responding, token valid"
            return 0
            ;;
        401)
            echo "[$LOG_TAG] $(date -Is) ERROR — 401 Unauthorized, token expired or invalid"
            echo "[$LOG_TAG] Action: run 'claude setup-token' to generate a new token"
            return 1
            ;;
        000)
            echo "[$LOG_TAG] $(date -Is) WARN — proxy not reachable at ${PROXY_URL}"
            echo "[$LOG_TAG] Action: check if CLIProxyAPI is running"
            return 1
            ;;
        *)
            echo "[$LOG_TAG] $(date -Is) WARN — unexpected HTTP ${http_code}"
            return 1
            ;;
    esac
}

if [[ "${1:-}" == "--once" ]]; then
    _check
    exit $?
fi

# ── Continuous mode ──
echo "[$LOG_TAG] Starting continuous monitoring (every 30 min)"
while true; do
    _check || true
    sleep 1800
done
