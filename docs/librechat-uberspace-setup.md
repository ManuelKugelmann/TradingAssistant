# LibreChat Lite → Uberspace: Step-by-Step Instructions

Complete deployment guide: GitHub repo → CI releases → Uberspace hosting with MCP servers and git-versioned data storage.

---

## Overview

```
Dev (Codespace/WSL)
  │ push code
  ▼
GitHub repo ──tag──▶ CI builds frontend + bundles tar ──▶ GitHub Release
                                                              │
                                   ┌──────────────────────────┘
                                   ▼
                            Uberspace (runtime)
                            ├─ LibreChat (:3080)
                            ├─ MCP: filesystem  → ~/TradeAssistant_Data/files/
                            ├─ MCP: memory      → ~/TradeAssistant_Data/memory.jsonl
                            ├─ MCP: sqlite      → ~/TradeAssistant_Data/data.db
                            └─ cron: git sync   → GitHub (private data repo)
                                    │
                              ┌─────┼──────┐
                              ▼     ▼      ▼
                         MongoDB  Cloud   Data
                         Atlas    LLMs    backup
```

---

## Phase 1: GitHub Setup

### 1.1 Create the bootstrap repo

```bash
# Option A: Unzip the package
unzip librechat-uberspace.zip
cd librechat-uberspace
git init && git add -A && git commit -m "init"

# Option B: Create repo on GitHub first, then push
git remote add origin git@github.com:YOUR_USER/librechat-uberspace.git
git push -u origin main
```

### 1.2 Configure repo secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value | Required |
|---|---|---|
| `UBERSPACE_HOST` | `yourname.uber.space` | For auto-deploy |
| `UBERSPACE_USER` | Your SSH username | For auto-deploy |
| `UBERSPACE_SSH_KEY` | Private SSH key (entire file content) | For auto-deploy |
| `GH_DEPLOY_TOKEN` | GitHub PAT with `repo` scope | For private repos |

Auto-deploy is optional — you can also manually run `bootstrap.sh` on Uberspace.

### 1.3 Create a GitHub environment

Go to **Settings → Environments → New environment** → name it `uberspace`.
This gates the deploy job and lets you add environment-specific secrets.

---

## Phase 2: MongoDB Atlas

### 2.1 Create free cluster

1. Go to https://cloud.mongodb.com
2. Create organization → project → **Build a Database**
3. Choose **M0 (Free)** — shared tier, 512 MB
4. Pick region closest to your Uberspace host (likely EU)
5. Create database user: username + strong password

### 2.2 Network access

1. **Network Access → Add IP Address**
2. Choose **Allow Access from Anywhere** (`0.0.0.0/0`)
3. Uberspace has no static IP — this is expected. Auth is enforced via connection string.

### 2.3 Get connection string

1. **Connect → Drivers** → copy URI
2. Replace `<password>` with your database user password
3. Append `/LibreChat` as the database name

```
mongodb+srv://user:password@cluster0.xxxxx.mongodb.net/LibreChat
```

---

## Phase 3: First Deploy to Uberspace

### 3.1 SSH setup

```bash
# Generate SSH key if needed
ssh-keygen -t ed25519 -C "uberspace"

# Copy public key to Uberspace dashboard or:
ssh-copy-id YOUR_USER@YOUR_HOST.uber.space

# Connect
ssh YOUR_USER@YOUR_HOST.uber.space
```

### 3.2 Set Node.js version

```bash
uberspace tools version use node 22
node --version   # verify: v22.x.x
```

### 3.3 npm global prefix (Uberspace requirement)

```bash
mkdir -p ~/.npm-global
npm config set prefix ~/.npm-global
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 3.4 Create first release

Before deploying, you need at least one release. On your dev machine:

```bash
git tag v0.1.0
git push --tags
# Wait for CI to complete → release with bundle appears
```

Or trigger manually: **Actions → Build & Release → Run workflow**

### 3.5 Install on Uberspace

```bash
# Set repo (required)
export LIBRECHAT_REPO="YOUR_USER/librechat-uberspace"

# For private repos:
export GH_TOKEN="ghp_xxxxxxxxxxxx"

# Run bootstrap
curl -sL "https://github.com/$LIBRECHAT_REPO/releases/latest/download/bootstrap.sh" | bash
```

### 3.6 Configure .env

```bash
nano ~/LibreChat/.env
```

**Required settings:**
```bash
MONGO_URI=mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/LibreChat
# CREDS_KEY, CREDS_IV, JWT_SECRET, JWT_REFRESH_SECRET are auto-generated
```

**Add your LLM API keys** (uncomment the ones you use):
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_KEY=...
```

### 3.7 Configure MCP paths

```bash
nano ~/LibreChat/librechat.yaml
```

Replace all `/home/user/` with your actual home path (`/home/YOUR_USER/`).
The setup script tries to do this automatically, but verify.

### 3.8 Start

```bash
supervisorctl start librechat

# Verify
supervisorctl status librechat   # should show RUNNING
curl -s http://127.0.0.1:3080 | head -5
```

### 3.9 Access

```
https://YOUR_USER.uber.space
```

Register your first account — this becomes the admin.

---

## Phase 4: Git-Versioned Data Storage

### 4.1 Create private data repo

Go to https://github.com/new:
- Name: `TradeAssistant_Data`
- Visibility: **Private**
- Do NOT initialize with README

### 4.2 Set up SSH key on Uberspace

```bash
# Check for existing key
ls ~/.ssh/id_ed25519.pub

# If none, generate:
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519

# Add public key to GitHub → Settings → SSH Keys
cat ~/.ssh/id_ed25519.pub
```

### 4.3 Run data repo setup

```bash
bash ~/LibreChat/scripts/setup-data-repo.sh YOUR_USER/TradeAssistant_Data
```

This script:
- Clones/initializes `~/TradeAssistant_Data/` as a git repo
- Creates `files/` directory for filesystem MCP
- Sets up `.gitignore` for large binaries
- Adds cron job: auto-sync every 15 minutes

### 4.4 Verify cron

```bash
crontab -l | grep TradeAssistant_Data-sync
# Should show: */15 * * * * cd ~/TradeAssistant_Data && git add -A && ...
```

### 4.5 What gets versioned

| Path | MCP Server | Content |
|---|---|---|
| `~/TradeAssistant_Data/files/` | `server-filesystem` | Documents, exports, CSV files |
| `~/TradeAssistant_Data/memory.jsonl` | `server-memory` | Knowledge graph (entities + relations) |
| `~/TradeAssistant_Data/data.db` | `mcp-sqlite` | SQLite database (logs, research, notes) |

View history: `cd ~/TradeAssistant_Data && git log --oneline`

---

## Phase 5: Day-to-Day Operations

### 5.1 The `ta` command

After install, `~/bin/ta` provides shortcuts (also available as `~/bin/TradeAssistant`):

```bash
ta help       # show all commands
ta s          # status + version
ta l          # tail live logs
ta r          # restart service
ta v          # installed version
ta u          # update to latest release
ta pull       # quick update via git pull (dev)
ta rb         # rollback to previous version
ta sync       # force git-sync data now
ta env        # edit .env
ta yaml       # edit librechat.yaml
```

### 5.2 Update workflow

On dev machine:
```bash
# Merge upstream changes, fix conflicts, test
git fetch upstream && git merge upstream/main
git push
git tag v0.2.0 && git push --tags
```

On Uberspace (if auto-deploy not configured):
```bash
ta u
```

### 5.3 Rollback

```bash
ta rb
# Restores ~/LibreChat.prev → ~/LibreChat and restarts
```

### 5.4 Monitoring

```bash
# Service status
supervisorctl status librechat

# Live logs
ta l

# Memory usage
free -h

# Disk usage
du -sh ~/LibreChat ~/TradeAssistant_Data
```

---

## Phase 6: Adding More MCP Servers

Edit `~/LibreChat/librechat.yaml` and add new servers:

```yaml
mcpServers:
  # ... existing servers ...

  # Example: Brave Search
  brave-search:
    command: npx
    args:
      - -y
      - "@anthropic-ai/mcp-server-brave-search"
    env:
      BRAVE_API_KEY: "${BRAVE_API_KEY}"

  # Example: Custom SSE server (remote)
  my-remote-mcp:
    type: sse
    url: "https://my-mcp-server.example.com/sse"
    timeout: 30000
```

Then restart: `ta r`

For stdio MCP servers that need Python: check if `python3` is available on Uberspace (`python3 --version`). If the MCP needs `uvx`, install via `pip install uv --break-system-packages`.

---

## Troubleshooting

### LibreChat won't start
```bash
# Check logs for errors
supervisorctl tail librechat stderr
# Common: wrong MONGO_URI, missing API key, port conflict
```

### Out of memory (killed by Uberspace)
```bash
# Check if process was OOM-killed
dmesg | tail -20
# Solution: already configured --max-old-space-size=1024 in supervisord
# If still dying: reduce to 768
```

### MCP server-memory ignores MEMORY_FILE_PATH
Known npx caching bug in some versions. Workaround:
```bash
# Find where npx actually writes it
find ~/.npm/_npx -name "memory.jsonl" 2>/dev/null
# Symlink it
ln -sf /path/found/memory.jsonl ~/TradeAssistant_Data/memory.jsonl
```

### MongoDB connection fails
```bash
# Test from Uberspace
node -e "const {MongoClient}=require('mongodb'); MongoClient.connect('YOUR_URI').then(()=>console.log('ok')).catch(e=>console.error(e))"
# Check: Atlas Network Access allows 0.0.0.0/0
```

### Git data sync not pushing
```bash
# Manual test
cd ~/TradeAssistant_Data
git add -A && git status
git push   # check for SSH key issues
# Verify: ssh -T git@github.com
```

### Port conflict
```bash
# Check what's using 3080
lsof -i :3080
# Re-register web backend
uberspace web backend set / --http --port 3080
```

---

## Security Checklist

- [ ] `.env` has `chmod 600` (setup.sh does this, verify)
- [ ] MongoDB Atlas user has minimal permissions (readWrite on LibreChat db only)
- [ ] API keys not committed to any repo
- [ ] Data repo is **private** on GitHub
- [ ] Registration disabled after creating your account (`ALLOW_REGISTRATION=false`)
- [ ] SSH key on Uberspace is ed25519, no passphrase (needed for cron git push)

---

## Cost Summary

| Service | Cost |
|---|---|
| Uberspace | ~5€/mo (pay what you want, min 1€) |
| MongoDB Atlas M0 | Free (512 MB) |
| GitHub (private repos) | Free |
| Cloud LLM APIs | Per-use |
| **Total infrastructure** | **~5€/mo** |

---

## File Manifest

```
librechat-uberspace/
├── .github/workflows/
│   └── release.yml              CI: build + bundle + optional auto-deploy
├── .devcontainer/
│   └── devcontainer.json        Codespaces dev environment
├── config/
│   ├── librechat.yaml           MCP servers + LibreChat config
│   └── .env.uberspace           Reference .env (not deployed)
├── scripts/
│   ├── bootstrap.sh             curl | bash entry point
│   ├── setup.sh                 Install/update with atomic swap
│   ├── setup-data-repo.sh       Git-versioned data directory
│   └── TradeAssistant.sh         Ops shortcuts (installed as 'ta')
├── .gitignore
└── README.md
```
