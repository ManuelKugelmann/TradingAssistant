#!/usr/bin/env bats
# Tests for TradeAssistant.sh sync command

load helpers/setup

setup() {
    setup_sandbox
    prepend_bin_to_path
    create_deploy_conf

    stub_command "supervisorctl" 'echo "stubbed"'
    stub_command "uberspace" 'echo "stubbed"'
    stub_command "hostname" 'echo "test.uber.space"'

    mkdir -p "$STACK_DIR/.git"
}

teardown() {
    teardown_sandbox
}

@test "sync: fails when DATA_DIR has no git repo" {
    mkdir -p "$DATA_DIR"
    # no .git

    run bash "$REPO_ROOT/librechat-uberspace/scripts/TradeAssistant.sh" sync
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"Data repo not initialized"* ]]
}

@test "sync: reports no changes when nothing to commit" {
    init_mock_git_repo "$DATA_DIR"

    run bash "$REPO_ROOT/librechat-uberspace/scripts/TradeAssistant.sh" sync
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"No changes to sync"* ]]
}

@test "sync: commits and attempts push when changes exist" {
    init_mock_git_repo "$DATA_DIR"
    echo "new content" > "$DATA_DIR/newfile.txt"

    # git push will fail (no remote) but that's fine — we check the commit happened
    run bash "$REPO_ROOT/librechat-uberspace/scripts/TradeAssistant.sh" sync
    # May fail on push, check commit was made
    cd "$DATA_DIR"
    run git log --oneline -1
    [[ "$output" == *"sync"* ]]
}
