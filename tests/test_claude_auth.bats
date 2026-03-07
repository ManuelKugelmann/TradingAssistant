#!/usr/bin/env bats
# Tests for claude-auth-daemon.sh — token health monitoring

load helpers/setup

DAEMON="$REPO_ROOT/librechat-uberspace/scripts/claude-auth-daemon.sh"

setup() {
    setup_sandbox
    prepend_bin_to_path
}

teardown() {
    teardown_sandbox
}

# ── Token loading ──

@test "daemon exits with error when no token set" {
    unset CLAUDE_CODE_OAUTH_TOKEN
    run bash "$DAEMON" --once
    [[ "$status" -eq 1 ]]
    [[ "$output" == *"CLAUDE_CODE_OAUTH_TOKEN not set"* ]]
    [[ "$output" == *"claude setup-token"* ]]
}

@test "daemon loads token from environment variable" {
    export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-testtoken"
    # Stub curl to simulate proxy not reachable (no proxy running in test)
    stub_command "curl" 'printf "000"'

    run bash "$DAEMON" --once
    # Exits non-zero because proxy is not reachable, but doesn't fail on token loading
    [[ "$output" == *"proxy not reachable"* ]]
    [[ "$output" != *"CLAUDE_CODE_OAUTH_TOKEN not set"* ]]
}

@test "daemon loads token from ~/.claude-auth.env file" {
    unset CLAUDE_CODE_OAUTH_TOKEN
    echo "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-fromfile" > "$HOME/.claude-auth.env"
    stub_command "curl" 'printf "000"'

    run bash "$DAEMON" --once
    # Should not complain about missing token
    [[ "$output" != *"CLAUDE_CODE_OAUTH_TOKEN not set"* ]]
    [[ "$output" == *"proxy not reachable"* ]]
}

# ── HTTP status handling ──

@test "daemon reports OK on HTTP 200" {
    export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-testtoken"
    stub_command "curl" 'printf "200"'

    run bash "$DAEMON" --once
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"OK"* ]]
    [[ "$output" == *"proxy responding"* ]]
}

@test "daemon reports error on HTTP 401" {
    export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-testtoken"
    stub_command "curl" 'printf "401"'

    run bash "$DAEMON" --once
    [[ "$status" -eq 1 ]]
    [[ "$output" == *"401 Unauthorized"* ]]
    [[ "$output" == *"expired"* ]]
    [[ "$output" == *"claude setup-token"* ]]
}

@test "daemon reports unreachable on connection failure (HTTP 000)" {
    export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-testtoken"
    stub_command "curl" 'printf "000"'

    run bash "$DAEMON" --once
    [[ "$status" -eq 1 ]]
    [[ "$output" == *"proxy not reachable"* ]]
    [[ "$output" == *"CLIProxyAPI"* ]]
}

@test "daemon reports unexpected HTTP codes" {
    export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-testtoken"
    stub_command "curl" 'printf "503"'

    run bash "$DAEMON" --once
    [[ "$status" -eq 1 ]]
    [[ "$output" == *"unexpected HTTP 503"* ]]
}

# ── Custom proxy URL ──

@test "daemon uses CLIPROXY_URL when set" {
    export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-testtoken"
    export CLIPROXY_URL="http://localhost:9999"
    # Stub curl to check the URL contains our custom port
    stub_command "curl" '
        if echo "$@" | grep -q "localhost:9999"; then
            printf "200"
        else
            printf "000"
        fi
    '

    run bash "$DAEMON" --once
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"OK"* ]]
}

# ── Output format ──

@test "daemon output includes timestamp and log tag" {
    export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-testtoken"
    stub_command "curl" 'printf "200"'

    run bash "$DAEMON" --once
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"[claude-auth]"* ]]
}

# ── Syntax check ──

@test "claude-auth-daemon.sh passes syntax check" {
    run bash -n "$DAEMON"
    [[ "$status" -eq 0 ]]
}
