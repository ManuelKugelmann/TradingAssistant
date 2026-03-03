#!/bin/bash
# bootstrap-uberspace.sh — Setup MCP signals stack on Uberspace
set -euo pipefail

# ── Load central config ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="${SCRIPT_DIR}/../deploy.conf"
[[ -f "$CONF" ]] && source "$CONF"

echo "🚀 MCP Servers — Uberspace Bootstrap"
echo "   Host: ${UBER_HOST:-$(hostname -f)}"
echo "   Install dir: $STACK_DIR"

mkdir -p "$STACK_DIR" ~/logs

# ── Python venv ──
cd "$STACK_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# ── Node.js ──
uberspace tools version use node "$NODE_VERSION" 2>/dev/null || true

# ── Copy .env ──
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  Edit .env with your API keys and MONGO_URI"
fi

# ── Register supervisord services for domain servers ──
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

# ── Signals store ──
cat > ~/etc/services.d/mcp-store.ini << EOF
[program:mcp-store]
directory=${STACK_DIR}
command=${STACK_DIR}/venv/bin/python src/store/server.py
autostart=false
autorestart=true
stderr_logfile=%(ENV_HOME)s/logs/mcp-store.err.log
stdout_logfile=%(ENV_HOME)s/logs/mcp-store.out.log
EOF

supervisorctl reread
echo "✅ Stack registered. Start with:"
echo "   supervisorctl start mcp-store"
echo "   supervisorctl start mcp-weather"
echo "   supervisorctl start mcp-disasters"
echo ""
echo "📋 Status: supervisorctl status"
