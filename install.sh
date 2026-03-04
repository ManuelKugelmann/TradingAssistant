#!/bin/bash
# install.sh — Thin shim, delegates to TradeAssistant.sh install
#
# Fresh install:
#   curl -sL https://raw.githubusercontent.com/ManuelKugelmann/TradingAssistant/main/install.sh | bash
#
# Or with a token for private repos:
#   curl -sL ... | GH_TOKEN=ghp_xxx bash
#
# The real logic lives in TradeAssistant.sh (installed as ~/bin/ta).
set -euo pipefail

SCRIPT_URL="https://raw.githubusercontent.com/${GH_USER:-ManuelKugelmann}/${GH_REPO:-TradingAssistant}/${BRANCH:-main}/librechat-uberspace/scripts/TradeAssistant.sh"

# If ta is already installed locally, use it
if command -v ta &>/dev/null; then
    exec ta install
fi

# Otherwise fetch and run
exec bash <(curl -sfL "$SCRIPT_URL") install
