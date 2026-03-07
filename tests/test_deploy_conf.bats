#!/usr/bin/env bats
# Tests for deploy.conf — central configuration loading

load helpers/setup

setup() {
    setup_sandbox
}

teardown() {
    teardown_sandbox
}

@test "deploy.conf sets all required variables" {
    source "$REPO_ROOT/deploy.conf"

    [[ -n "$UBER_USER" ]]
    [[ -n "$UBER_HOST" ]]
    [[ -n "$GH_USER" ]]
    [[ -n "$GH_REPO" ]]
    [[ -n "$GH_REPO_DATA" ]]
    [[ -n "$STACK_DIR" ]]
    [[ -n "$APP_DIR" ]]
    [[ -n "$DATA_DIR" ]]
    [[ -n "$LC_PORT" ]]
    [[ -n "$NODE_VERSION" ]]
}

@test "deploy.conf default UBER_HOST derives from UBER_USER" {
    unset UBER_HOST
    export UBER_USER="myuser"
    source "$REPO_ROOT/deploy.conf"

    [[ "$UBER_HOST" == "myuser.uber.space" ]]
}

@test "deploy.conf allows environment overrides" {
    export UBER_USER="custom"
    export LC_PORT="9999"
    export NODE_VERSION="20"
    source "$REPO_ROOT/deploy.conf"

    [[ "$UBER_USER" == "custom" ]]
    [[ "$LC_PORT" == "9999" ]]
    [[ "$NODE_VERSION" == "20" ]]
}

@test "deploy.conf GH_REPO defaults to TradingAssistant" {
    unset GH_REPO
    source "$REPO_ROOT/deploy.conf"

    [[ "$GH_REPO" == "TradingAssistant" ]]
}

@test "deploy.conf passes bash syntax check" {
    run bash -n "$REPO_ROOT/deploy.conf"
    [[ "$status" -eq 0 ]]
}
