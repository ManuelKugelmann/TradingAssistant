#!/usr/bin/env bats
# Tests for bootstrap.sh — syntax and basic validation

load helpers/setup

setup() {
    setup_sandbox
}

teardown() {
    teardown_sandbox
}

@test "bootstrap.sh passes syntax check" {
    run bash -n "$REPO_ROOT/librechat-uberspace/scripts/bootstrap.sh"
    [[ "$status" -eq 0 ]]
}

@test "all shell scripts pass syntax check" {
    local scripts=(
        "$REPO_ROOT/librechat-uberspace/scripts/TradeAssistant.sh"
        "$REPO_ROOT/librechat-uberspace/scripts/setup.sh"
        "$REPO_ROOT/librechat-uberspace/scripts/setup-data-repo.sh"
        "$REPO_ROOT/librechat-uberspace/scripts/bootstrap.sh"
        "$REPO_ROOT/scripts/nightly-git-commit.sh"
    )
    for script in "${scripts[@]}"; do
        run bash -n "$script"
        [[ "$status" -eq 0 ]] || {
            echo "Syntax error in: $script"
            echo "$output"
            return 1
        }
    done
}
