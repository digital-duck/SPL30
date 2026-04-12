#!/usr/bin/env bash
# test_04_test_code.sh
# Unit test for 04_test_code.spl
# Tests: good code → [PASSED], buggy code → [FAILED]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs/04_test_code"
mkdir -p "$LOG_DIR"

SPEC=$(cat "$SCRIPT_DIR/mock/spec_clear.txt")
CODE_GOOD=$(cat "$SCRIPT_DIR/mock/code_good.py")
CODE_BUGGY=$(cat "$SCRIPT_DIR/mock/code_buggy.py")
MODEL="${1:-llama3.2}"
PASS=0; FAIL=0

run_test() {
    local name="$1" code="$2" expected_token="$3"
    echo "  [$name] running ..."
    output=$(spl3 run "$PIPELINE_DIR/04_test_code.spl" \
        --adapter ollama \
        --param "code=$code" \
        --param "spec=$SPEC" \
        --param "lang=python" \
        --param "model=$MODEL" \
        --param "log_dir=$LOG_DIR/$name" \
        2>&1)
    if echo "$output" | grep -q "$expected_token"; then
        echo "  [$name] PASS — found '$expected_token'"
        PASS=$((PASS + 1))
    else
        echo "  [$name] FAIL — expected '$expected_token' in output"
        echo "  output: $(echo "$output" | tail -5)"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== 04_test_code | model=$MODEL ==="
run_test "good_code"  "$CODE_GOOD"  "[PASSED]"
run_test "buggy_code" "$CODE_BUGGY" "[FAILED]"

echo "--- result: $PASS passed, $FAIL failed ---"
[ "$FAIL" -eq 0 ]
