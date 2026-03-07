#!/usr/bin/env bats
# Tests for TradeAssistant.sh — proxy subcommands (CLIProxyAPI / Claude token wrapper)

load helpers/setup

TA="$REPO_ROOT/librechat-uberspace/scripts/TradeAssistant.sh"

setup() {
    setup_sandbox
    prepend_bin_to_path
    create_deploy_conf

    # Stub commands
    stub_command "supervisorctl" 'echo "stubbed supervisorctl $*"'
    stub_command "hostname" 'echo "test.uber.space"'
    stub_command "npm" 'echo "stubbed npm $*"'
    stub_command "cliproxyapi" 'echo "0.1.0"'

    # Create .git so auto-install detection is skipped
    mkdir -p "$STACK_DIR/.git"

    # Copy auth daemon so proxy setup can install it
    mkdir -p "$STACK_DIR/librechat-uberspace/scripts"
    cp "$REPO_ROOT/librechat-uberspace/scripts/claude-auth-daemon.sh" \
       "$STACK_DIR/librechat-uberspace/scripts/claude-auth-daemon.sh"
}

teardown() {
    teardown_sandbox
}

# ── proxy help ──

@test "proxy without subcommand shows help" {
    run bash "$TA" proxy
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"ta proxy setup"* ]]
    [[ "$output" == *"ta proxy start"* ]]
    [[ "$output" == *"ta proxy stop"* ]]
    [[ "$output" == *"ta proxy status"* ]]
    [[ "$output" == *"ta proxy test"* ]]
    [[ "$output" == *"ta proxy token"* ]]
}

@test "help command lists proxy in command overview" {
    run bash "$TA" help
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"proxy"* ]]
}

# ── proxy setup ──

@test "proxy setup creates config file" {
    run bash "$TA" proxy setup
    [[ "$status" -eq 0 ]]
    [[ -f "$HOME/.cli-proxy-api/config.yaml" ]]
    # Verify config content
    grep -q "port: 8317" "$HOME/.cli-proxy-api/config.yaml"
    grep -q "providers: \[\]" "$HOME/.cli-proxy-api/config.yaml"
}

@test "proxy setup is idempotent — does not overwrite existing config" {
    mkdir -p "$HOME/.cli-proxy-api"
    echo "port: 9999" > "$HOME/.cli-proxy-api/config.yaml"

    run bash "$TA" proxy setup
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"Config already exists"* ]]
    # Original config preserved
    grep -q "port: 9999" "$HOME/.cli-proxy-api/config.yaml"
}

@test "proxy setup warns when no token file exists" {
    run bash "$TA" proxy setup
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"No token found"* ]]
    [[ "$output" == *"claude setup-token"* ]]
}

@test "proxy setup does not warn when token file exists" {
    echo "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-testtoken1234" > "$HOME/.claude-auth.env"

    run bash "$TA" proxy setup
    [[ "$status" -eq 0 ]]
    [[ "$output" != *"No token found"* ]]
}

@test "proxy setup registers supervisord service without token" {
    run bash "$TA" proxy setup
    [[ "$status" -eq 0 ]]
    [[ -f "$HOME/etc/services.d/cliproxyapi.ini" ]]
    grep -q "\[program:cliproxyapi\]" "$HOME/etc/services.d/cliproxyapi.ini"
    # Without token file, should use direct command (not bash -c wrapper)
    grep -q "command=cliproxyapi" "$HOME/etc/services.d/cliproxyapi.ini"
}

@test "proxy setup registers supervisord service with token (bash wrapper)" {
    echo "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-testtoken1234" > "$HOME/.claude-auth.env"

    run bash "$TA" proxy setup
    [[ "$status" -eq 0 ]]
    [[ -f "$HOME/etc/services.d/cliproxyapi.ini" ]]
    # With token file, should use bash -c to source the env
    grep -q "bash -c" "$HOME/etc/services.d/cliproxyapi.ini"
    grep -q "source" "$HOME/etc/services.d/cliproxyapi.ini"
}

@test "proxy setup installs auth daemon to ~/bin" {
    run bash "$TA" proxy setup
    [[ "$status" -eq 0 ]]
    [[ -f "$HOME/bin/claude-auth-daemon.sh" ]]
    [[ -x "$HOME/bin/claude-auth-daemon.sh" ]]
}

@test "proxy setup shows next steps" {
    run bash "$TA" proxy setup
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"Next steps"* ]]
    [[ "$output" == *"ta proxy start"* ]]
    [[ "$output" == *"ta proxy test"* ]]
}

# ── proxy start/stop/status ──

@test "proxy start calls supervisorctl start" {
    run bash "$TA" proxy start
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"stubbed supervisorctl start cliproxyapi"* ]]
}

@test "proxy stop calls supervisorctl stop" {
    run bash "$TA" proxy stop
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"stubbed supervisorctl stop cliproxyapi"* ]]
}

@test "proxy status calls supervisorctl status" {
    run bash "$TA" proxy status
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"stubbed supervisorctl status cliproxyapi"* ]]
}

# ── proxy test ──

@test "proxy test reports unreachable when no proxy running" {
    # Stub curl to return 000 (connection refused)
    stub_command "curl" 'echo "000"'

    run bash "$TA" proxy test
    [[ "$status" -eq 1 ]]
    [[ "$output" == *"not reachable"* ]]
}

# ── proxy token ──

@test "proxy token shows info when token file exists" {
    echo "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-abcdefgh_rest_of_token" > "$HOME/.claude-auth.env"

    run bash "$TA" proxy token
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"sk-ant-oat01-abcdefgh"* ]]
    [[ "$output" == *".claude-auth.env"* ]]
    [[ "$output" == *"expire"* ]]
}

@test "proxy token warns when no token file" {
    rm -f "$HOME/.claude-auth.env"

    run bash "$TA" proxy token
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"No token file"* ]]
    [[ "$output" == *"claude setup-token"* ]]
}

@test "proxy token does not leak full token" {
    echo "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-abcdefghSECRETSECRETSECRETSECRET" > "$HOME/.claude-auth.env"

    run bash "$TA" proxy token
    [[ "$status" -eq 0 ]]
    # Should show prefix but not the full token
    [[ "$output" == *"sk-ant-oat01-abcdefgh..."* ]]
    [[ "$output" != *"SECRETSECRET"* ]]
}
