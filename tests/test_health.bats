#!/usr/bin/env bats
# Tests for TradeAssistant.sh — check/health command

load helpers/setup

TA="$REPO_ROOT/librechat-uberspace/scripts/TradeAssistant.sh"

setup() {
    setup_sandbox
    prepend_bin_to_path
    create_deploy_conf

    # Stub commands
    stub_command "supervisorctl" 'echo "stubbed supervisorctl $*"'
    stub_command "hostname" 'echo "test.uber.space"'
    stub_command "node" 'echo "v22.0.0"'
    stub_command "crontab" 'echo "no crontab"'

    # Stub curl to return 000 (no services running in test)
    stub_command "curl" 'echo "000"'

    # Create .git so auto-install detection is skipped
    mkdir -p "$STACK_DIR/.git"
}

teardown() {
    teardown_sandbox
}

# ── Basic invocation ──

@test "check command runs without error" {
    # Minimal setup: deploy.conf exists, no services
    run bash "$TA" check
    # May exit 1 due to FAILs (no venv, no app), but should not crash
    [[ "$output" == *"Health Check"* ]]
    [[ "$output" == *"Summary"* ]]
}

@test "health alias works" {
    run bash "$TA" health
    [[ "$output" == *"Health Check"* ]]
    [[ "$output" == *"Summary"* ]]
}

@test "help mentions check command" {
    run bash "$TA" help
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"check"* ]]
    [[ "$output" == *"Health check"* ]]
}

# ── Infrastructure checks ──

@test "check detects stack repo" {
    run bash "$TA" check
    [[ "$output" == *"PASS"*"Stack repo"* ]]
}

@test "check detects deploy.conf" {
    run bash "$TA" check
    [[ "$output" == *"PASS"*"deploy.conf"* ]]
}

@test "check detects missing deploy.conf" {
    rm -f "$STACK_DIR/deploy.conf"
    run bash "$TA" check
    [[ "$output" == *"FAIL"*"deploy.conf"* ]]
}

@test "check detects missing venv" {
    run bash "$TA" check
    [[ "$output" == *"FAIL"*"venv"* ]]
}

@test "check detects present venv" {
    mkdir -p "$STACK_DIR/venv/bin"
    cat > "$STACK_DIR/venv/bin/python" << 'PYEOF'
#!/bin/bash
if [[ "$1" == "--version" ]]; then echo "Python 3.11.0"; exit 0; fi
if [[ "$1" == "-c" ]]; then exit 0; fi
PYEOF
    chmod +x "$STACK_DIR/venv/bin/python"
    run bash "$TA" check
    [[ "$output" == *"PASS"*"Python venv"* ]]
}

@test "check detects Node.js" {
    run bash "$TA" check
    [[ "$output" == *"PASS"*"Node.js"* ]]
}

# ── App checks ──

@test "check detects missing LibreChat" {
    run bash "$TA" check
    [[ "$output" == *"FAIL"*"LibreChat not installed"* ]]
}

@test "check detects installed LibreChat" {
    echo "v1.0.0" > "$APP_DIR/.version"
    run bash "$TA" check
    [[ "$output" == *"PASS"*"LibreChat installed: v1.0.0"* ]]
}

@test "check detects LibreChat .env with MONGO_URI" {
    echo "MONGO_URI=mongodb+srv://test" > "$APP_DIR/.env"
    run bash "$TA" check
    [[ "$output" == *"PASS"*"MONGO_URI"* ]]
}

@test "check warns on LibreChat .env without MONGO_URI" {
    echo "SOME_OTHER=value" > "$APP_DIR/.env"
    run bash "$TA" check
    [[ "$output" == *"WARN"*"MONGO_URI not set"* ]]
}

@test "check detects librechat.yaml with mcpServers" {
    echo "mcpServers:" > "$APP_DIR/librechat.yaml"
    run bash "$TA" check
    [[ "$output" == *"PASS"*"librechat.yaml with MCP servers"* ]]
}

# ── Data checks ──

@test "check detects data dir with git" {
    mkdir -p "$DATA_DIR"
    init_mock_git_repo "$DATA_DIR"
    run bash "$TA" check
    [[ "$output" == *"PASS"*"Data dir: git-tracked"* ]]
}

@test "check warns on data dir without git" {
    mkdir -p "$DATA_DIR"
    run bash "$TA" check
    [[ "$output" == *"WARN"*"not git-tracked"* ]]
}

@test "check detects profiles" {
    mkdir -p "$STACK_DIR/profiles/global/countries"
    echo '{}' > "$STACK_DIR/profiles/global/countries/USA.json"
    echo '{}' > "$STACK_DIR/profiles/global/countries/DEU.json"
    run bash "$TA" check
    [[ "$output" == *"PASS"*"Profiles: 2 JSON files"* ]]
}

@test "check warns on empty profiles" {
    mkdir -p "$STACK_DIR/profiles"
    run bash "$TA" check
    [[ "$output" == *"WARN"*"no profiles found"* ]]
}

# ── Shell syntax checks ──

@test "check validates shell scripts syntax" {
    # Copy real scripts so syntax check has something to validate
    mkdir -p "$STACK_DIR/librechat-uberspace/scripts"
    for f in "$REPO_ROOT/librechat-uberspace/scripts/"*.sh; do
        cp "$f" "$STACK_DIR/librechat-uberspace/scripts/"
    done
    run bash "$TA" check
    [[ "$output" == *"PASS"*"Shell scripts: all pass syntax check"* ]]
}

@test "check detects shell syntax error" {
    mkdir -p "$STACK_DIR/librechat-uberspace/scripts"
    echo "if then broken" > "$STACK_DIR/librechat-uberspace/scripts/broken.sh"
    run bash "$TA" check
    [[ "$output" == *"FAIL"*"Syntax error: broken.sh"* ]]
}

# ── Connectivity (stubbed) ──

@test "check reports LibreChat HTTP unreachable" {
    run bash "$TA" check
    [[ "$output" == *"FAIL"*"LibreChat HTTP: not reachable"* ]]
}

@test "check skips CLIProxyAPI when not configured" {
    run bash "$TA" check
    [[ "$output" == *"SKIP"*"CLIProxyAPI: not configured"* ]]
}

@test "check tests CLIProxyAPI when token file exists" {
    echo "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-test" > "$HOME/.claude-auth.env"
    run bash "$TA" check
    [[ "$output" == *"FAIL"*"CLIProxyAPI: not reachable"* ]]
}

# ── Summary ──

@test "check shows pass/fail/warn counts" {
    run bash "$TA" check
    [[ "$output" == *"Total:"* ]]
    [[ "$output" == *"Pass:"* ]]
    [[ "$output" == *"Fail:"* ]]
    [[ "$output" == *"Warn:"* ]]
}

@test "check exits 1 when failures exist" {
    # Without LibreChat, venv, etc — guaranteed failures
    run bash "$TA" check
    [[ "$status" -eq 1 ]]
    [[ "$output" == *"Some checks failed"* ]]
}

@test "check shows --test tip when run without it" {
    run bash "$TA" check
    [[ "$output" == *"--test"* ]]
    [[ "$output" == *"ta check --test"* ]]
}
