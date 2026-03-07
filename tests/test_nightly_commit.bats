#!/usr/bin/env bats
# Tests for nightly-git-commit.sh — profile auto-commit script

load helpers/setup

setup() {
    setup_sandbox
    prepend_bin_to_path

    # Create a mock repo structure matching the script's expectations
    # nightly-git-commit.sh does: cd "$(dirname "$0")/.." (goes to repo root)
    export MOCK_REPO="$TEST_SANDBOX/mock_repo"
    mkdir -p "$MOCK_REPO/scripts" "$MOCK_REPO/profiles/countries"

    # Copy the script into the mock structure
    cp "$REPO_ROOT/scripts/nightly-git-commit.sh" "$MOCK_REPO/scripts/"

    # Init git repo
    init_mock_git_repo "$MOCK_REPO"
}

teardown() {
    teardown_sandbox
}

@test "nightly-git-commit.sh passes syntax check" {
    run bash -n "$REPO_ROOT/scripts/nightly-git-commit.sh"
    [[ "$status" -eq 0 ]]
}

@test "nightly commit: commits when profile changes exist" {
    echo '{"id":"TST","name":"Test"}' > "$MOCK_REPO/profiles/countries/TST.json"

    run bash "$MOCK_REPO/scripts/nightly-git-commit.sh"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"Committed profile changes"* ]]

    # Verify commit was made
    cd "$MOCK_REPO"
    run git log --oneline -1
    [[ "$output" == *"profile updates"* ]]
}

@test "nightly commit: no commit when no changes" {
    local before_hash
    before_hash=$(git -C "$MOCK_REPO" rev-parse HEAD)

    run bash "$MOCK_REPO/scripts/nightly-git-commit.sh"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"No profile changes"* ]]

    local after_hash
    after_hash=$(git -C "$MOCK_REPO" rev-parse HEAD)
    [[ "$before_hash" == "$after_hash" ]]
}

@test "nightly commit: only stages profiles directory" {
    # Create a file outside profiles/
    echo "unrelated" > "$MOCK_REPO/unrelated.txt"
    # Create a file inside profiles/
    echo '{"id":"NEW"}' > "$MOCK_REPO/profiles/countries/NEW.json"

    run bash "$MOCK_REPO/scripts/nightly-git-commit.sh"
    [[ "$status" -eq 0 ]]

    # Check that unrelated.txt is NOT committed
    cd "$MOCK_REPO"
    run git show --name-only HEAD
    [[ "$output" != *"unrelated.txt"* ]]
    [[ "$output" == *"profiles/"* ]]
}
