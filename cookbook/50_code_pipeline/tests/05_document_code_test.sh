#!/usr/bin/env bash
# test_05_document_code.sh
# Unit test for 05_document_code.spl
# Tests: documentation is generated with expected Markdown structure

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs/05_document_code"
mkdir -p "$LOG_DIR"

source "$SCRIPT_DIR/helpers.sh"

SPEC=$(cat "$SCRIPT_DIR/mock/spec_clear.txt")
CODE=$(cat "$SCRIPT_DIR/mock/code_good.py")
MODEL="${1:-llama3.2}"
PASS=0; FAIL=0

run_test() {
    local name="$1" expected_token="$2"
    local run_script="$LOG_DIR/$name/run.sh"
    save_run_script "$run_script" "$PIPELINE_DIR/05_document_code.spl" ollama \
        code "$CODE" spec "$SPEC" lang "python" model "$MODEL" log_dir "$LOG_DIR/$name"
    local -a cmd=(spl3 run "$PIPELINE_DIR/05_document_code.spl"
        --adapter ollama
        --param "code=$CODE"
        --param "spec=$SPEC"
        --param "lang=python"
        --param "model=$MODEL"
        --param "log_dir=$LOG_DIR/$name")
    echo "  [$name] running ..."
    echo "  CMD: ${cmd[*]}"
    echo "  RUN: $run_script"
    output=$("${cmd[@]}" 2>&1)
    if echo "$output" | grep -qi "$expected_token"; then
        echo "  [$name] PASS — found '$expected_token'"
        PASS=$((PASS + 1))
    else
        echo "  [$name] FAIL — expected '$expected_token' in output"
        echo "  output: $(echo "$output" | tail -5)"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== 05_document_code | model=$MODEL ==="
run_test "generate_docs" "## Overview\|## Parameters\|## Returns\|binary_search"

echo "--- result: $PASS passed, $FAIL failed ---"
[ "$FAIL" -eq 0 ]
