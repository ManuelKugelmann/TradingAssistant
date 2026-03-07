#!/usr/bin/env bats
# Tests for setup.sh — LibreChat install/update logic

load helpers/setup

setup() {
    setup_sandbox
    prepend_bin_to_path
    create_deploy_conf

    # Stub external commands
    stub_command "supervisorctl" 'echo "stubbed supervisorctl $*"'
    stub_command "uberspace" 'echo "stubbed uberspace $*"'
    stub_command "node" 'echo "v22.0.0"'
    stub_command "npm" 'echo "stubbed npm $*"'
    stub_command "hostname" 'echo "test.uber.space"'
    stub_command "python3" 'echo "stubbed python3 $*"'
}

# Helper: create a minimal source directory that passes setup.sh validation
create_src_app() {
    local src="${1:?}"
    mkdir -p "$src/config" "$src/scripts" "$src/node_modules/@modelcontextprotocol" "$src/api/server"
    echo "// stub" > "$src/api/server/index.js"
}

teardown() {
    teardown_sandbox
}

@test "setup.sh passes syntax check" {
    run bash -n "$REPO_ROOT/librechat-uberspace/scripts/setup.sh"
    [[ "$status" -eq 0 ]]
}

@test "setup.sh fails without arguments" {
    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup.sh"
    [[ "$status" -ne 0 ]]
}

@test "setup.sh install mode creates version file" {
    # Prepare a source directory with required files
    local src="$TEST_SANDBOX/src_app"
    create_src_app "$src"

    # Create .env.example
    cat > "$src/config/.env.example" <<'EOF'
CREDS_KEY=placeholder
CREDS_IV=placeholder
JWT_SECRET=placeholder
JWT_REFRESH_SECRET=placeholder
MONGO_URI=
EOF

    # Remove APP_DIR so install mode is triggered
    rm -rf "$APP_DIR"

    # Stub openssl for key generation
    stub_command "openssl" 'echo "deadbeef1234567890abcdef12345678"'

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup.sh" "$src" "v1.0.0"
    [[ "$status" -eq 0 ]]
    [[ -f "$APP_DIR/.version" ]]
    [[ "$(cat "$APP_DIR/.version")" == "v1.0.0" ]]
}

@test "setup.sh install mode generates .env with crypto keys" {
    local src="$TEST_SANDBOX/src_app"
    create_src_app "$src"
    cat > "$src/config/.env.example" <<'EOF'
CREDS_KEY=placeholder
CREDS_IV=placeholder
JWT_SECRET=placeholder
JWT_REFRESH_SECRET=placeholder
SEARCH=true
EOF
    rm -rf "$APP_DIR"
    stub_command "openssl" 'echo "abcdef0123456789abcdef0123456789"'

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup.sh" "$src" "v1.0.0"
    [[ "$status" -eq 0 ]]
    [[ -f "$APP_DIR/.env" ]]

    # Keys should be replaced (not "placeholder")
    run grep "^CREDS_KEY=" "$APP_DIR/.env"
    [[ "$output" != *"placeholder"* ]]

    # SEARCH should be false
    run grep "^SEARCH=" "$APP_DIR/.env"
    [[ "$output" == "SEARCH=false" ]]
}

@test "setup.sh update mode preserves .env" {
    # Set up existing APP_DIR (update mode)
    mkdir -p "$APP_DIR" "$APP_DIR/uploads"
    echo "EXISTING_KEY=keep_me" > "$APP_DIR/.env"
    echo "v0.9.0" > "$APP_DIR/.version"

    # Source directory
    local src="$TEST_SANDBOX/src_app"
    create_src_app "$src"

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup.sh" "$src" "v1.1.0"
    [[ "$status" -eq 0 ]]

    # .env should be preserved
    [[ -f "$APP_DIR/.env" ]]
    run grep "EXISTING_KEY=keep_me" "$APP_DIR/.env"
    [[ "$status" -eq 0 ]]

    # Version should be updated
    [[ "$(cat "$APP_DIR/.version")" == "v1.1.0" ]]

    # Previous version should be backed up
    [[ -d "${APP_DIR}.prev" ]]
}

@test "setup.sh creates supervisord service file on install" {
    local src="$TEST_SANDBOX/src_app"
    create_src_app "$src"
    cat > "$src/config/.env.example" <<'EOF'
CREDS_KEY=placeholder
CREDS_IV=placeholder
JWT_SECRET=placeholder
JWT_REFRESH_SECRET=placeholder
EOF
    rm -rf "$APP_DIR"
    stub_command "openssl" 'echo "deadbeef1234567890abcdef12345678"'

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup.sh" "$src" "v1.0.0"
    [[ "$status" -eq 0 ]]
    [[ -f "$HOME/etc/services.d/librechat.ini" ]]

    run grep "program:librechat" "$HOME/etc/services.d/librechat.ini"
    [[ "$status" -eq 0 ]]
}

@test "setup.sh creates data directory with .gitignore" {
    local src="$TEST_SANDBOX/src_app"
    create_src_app "$src"
    cat > "$src/config/.env.example" <<'EOF'
CREDS_KEY=placeholder
CREDS_IV=placeholder
JWT_SECRET=placeholder
JWT_REFRESH_SECRET=placeholder
EOF
    rm -rf "$APP_DIR"
    stub_command "openssl" 'echo "deadbeef1234567890abcdef12345678"'

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup.sh" "$src" "v1.0.0"
    [[ "$status" -eq 0 ]]
    [[ -d "$DATA_DIR/files" ]]
    [[ -f "$DATA_DIR/.gitignore" ]]
}

@test "setup.sh copies librechat.yaml and replaces __HOME__" {
    local src="$TEST_SANDBOX/src_app"
    create_src_app "$src"
    echo "path: __HOME__/data" > "$src/config/librechat.yaml"
    cat > "$src/config/.env.example" <<'EOF'
CREDS_KEY=placeholder
CREDS_IV=placeholder
JWT_SECRET=placeholder
JWT_REFRESH_SECRET=placeholder
EOF
    rm -rf "$APP_DIR"
    stub_command "openssl" 'echo "deadbeef1234567890abcdef12345678"'

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup.sh" "$src" "v1.0.0"
    [[ "$status" -eq 0 ]]
    [[ -f "$APP_DIR/librechat.yaml" ]]

    run grep "__HOME__" "$APP_DIR/librechat.yaml"
    [[ "$status" -ne 0 ]]  # __HOME__ should be replaced

    run grep "$HOME" "$APP_DIR/librechat.yaml"
    [[ "$status" -eq 0 ]]
}

@test "setup.sh rejects Node.js < 20" {
    # Override node stub to return old version
    stub_command "node" 'if [[ "$1" == "-v" ]]; then echo "v18.0.0"; else echo "v18.0.0"; fi'

    local src="$TEST_SANDBOX/src_app"
    mkdir -p "$src"
    rm -rf "$APP_DIR"

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup.sh" "$src" "v1.0.0"
    [[ "$status" -ne 0 ]]
    [[ "$output" == *"Node.js"* ]]
}
