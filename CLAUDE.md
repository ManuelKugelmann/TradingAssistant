# CLAUDE.md — Project context for Claude Code

## Project

**TradingAssistant** — LibreChat deployment with 15 MCP servers (3 utility + 1 signals store + 12 trading domain servers) on Uberspace.

## Naming

- **Repo**: `ManuelKugelmann/TradingAssistant`
- **Data repo**: `ManuelKugelmann/TradeAssistant_Data` (private, git-synced every 15 min)
- **Ops tool**: `TradeAssistant.sh` — installed as `~/bin/ta` (shorthand) and `~/bin/TradeAssistant` (symlink)
  - Usage: `ta help`, `ta status`, `ta update`, `ta pull`, `ta logs`, `ta restart`, etc.
- **Uberspace host**: `assist.uber.space`
- **Local data dir**: `~/TradeAssistant_Data/`
- **Stack dir**: `~/mcps/` (signals stack clone)
- **App dir**: `~/LibreChat/` (LibreChat installation)

## Key Files

- `deploy.conf` — central config, sourced by all scripts
- `install.sh` — one-liner installer (`curl ... | bash`)
- `librechat-uberspace/scripts/TradeAssistant.sh` — ops CLI tool
- `librechat-uberspace/scripts/setup.sh` — install/update with atomic swap
- `librechat-uberspace/scripts/setup-data-repo.sh` — data repo init + cron
- `librechat-uberspace/scripts/bootstrap.sh` — release download entry point
- `librechat-uberspace/config/librechat.yaml` — MCP server definitions
- `.github/workflows/release.yml` — CI: tag → build bundle → GitHub Release

## Dev Workflow

- Push to `main` → `ta pull` on server for dev updates
- Tag `vX.Y.Z` → CI builds release → `ta u` on server for prod updates
- Data syncs automatically via cron to `TradeAssistant_Data` repo
