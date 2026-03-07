#!/usr/bin/env bats
# Tests for setup-data-repo.sh — data repo initialization

load helpers/setup

setup() {
    setup_sandbox
    create_deploy_conf

    # Pre-create SSH key so script skips the interactive keygen + read prompt
    mkdir -p "$HOME/.ssh"
    ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" -q 2>/dev/null || {
        # Fallback if ssh-keygen not available: create fake key files
        touch "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_ed25519.pub"
    }

    # Create stubs directory separate from $HOME/bin to avoid PATH issues
    export STUBS_DIR="$TEST_SANDBOX/stubs"
    mkdir -p "$STUBS_DIR"

    # Git wrapper: intercept ls-remote, delegate rest to real git
    cat > "$STUBS_DIR/git" <<EOF
#!/bin/bash
if [[ "\$1" == "ls-remote" ]]; then exit 1; fi
exec $REAL_GIT "\$@"
EOF
    chmod +x "$STUBS_DIR/git"

    # Crontab stub
    cat > "$STUBS_DIR/crontab" <<EOF
#!/bin/bash
case "\$1" in
    -l) echo "" ;;
    -) cat > "$TEST_SANDBOX/crontab_written" ;;
esac
EOF
    chmod +x "$STUBS_DIR/crontab"

    # Hostname stub
    cat > "$STUBS_DIR/hostname" <<'EOF'
#!/bin/bash
echo "test.uber.space"
EOF
    chmod +x "$STUBS_DIR/hostname"

    export PATH="$STUBS_DIR:$PATH"
}

teardown() {
    teardown_sandbox
}

@test "setup-data-repo.sh passes syntax check" {
    run bash -n "$REPO_ROOT/librechat-uberspace/scripts/setup-data-repo.sh"
    [[ "$status" -eq 0 ]]
}

@test "setup-data-repo.sh creates directory structure" {
    rm -rf "$DATA_DIR"

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup-data-repo.sh" "TestUser/TestData"
    [[ "$status" -eq 0 ]]
    [[ -d "$DATA_DIR/files" ]]
    [[ -f "$DATA_DIR/.gitignore" ]]
    [[ -f "$DATA_DIR/README.md" ]]
}

@test "setup-data-repo.sh creates .gitignore with expected patterns" {
    rm -rf "$DATA_DIR"

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup-data-repo.sh" "TestUser/TestData"
    [[ "$status" -eq 0 ]]

    run grep '\.bin' "$DATA_DIR/.gitignore"
    [[ "$status" -eq 0 ]]
    run grep '\.zip' "$DATA_DIR/.gitignore"
    [[ "$status" -eq 0 ]]
    run grep '.DS_Store' "$DATA_DIR/.gitignore"
    [[ "$status" -eq 0 ]]
}

@test "setup-data-repo.sh sets up cron entry" {
    rm -rf "$DATA_DIR"

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup-data-repo.sh" "TestUser/TestData"
    [[ "$status" -eq 0 ]]
    [[ -f "$TEST_SANDBOX/crontab_written" ]]
    run grep "ta cron" "$TEST_SANDBOX/crontab_written"
    [[ "$status" -eq 0 ]]
}

@test "setup-data-repo.sh skips cron when already configured" {
    rm -rf "$DATA_DIR"

    # Override crontab stub to report existing cron
    cat > "$STUBS_DIR/crontab" <<EOF
#!/bin/bash
case "\$1" in
    -l) echo "*/15 * * * * \$HOME/bin/ta cron 2>&1 | logger -t ta-cron" ;;
    -) cat > "$TEST_SANDBOX/crontab_written" ;;
esac
EOF
    chmod +x "$STUBS_DIR/crontab"

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup-data-repo.sh" "TestUser/TestData"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"Cron already configured"* ]]
    [[ ! -f "$TEST_SANDBOX/crontab_written" ]]
}

@test "setup-data-repo.sh skips init when data repo already exists" {
    init_mock_git_repo "$DATA_DIR"
    mkdir -p "$DATA_DIR/files"

    # Override crontab to report existing cron
    cat > "$STUBS_DIR/crontab" <<EOF
#!/bin/bash
case "\$1" in
    -l) echo "*/15 * * * * ta cron" ;;
    -) cat > /dev/null ;;
esac
EOF
    chmod +x "$STUBS_DIR/crontab"

    run bash "$REPO_ROOT/librechat-uberspace/scripts/setup-data-repo.sh" "TestUser/TestData"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"already initialized"* ]]
}
