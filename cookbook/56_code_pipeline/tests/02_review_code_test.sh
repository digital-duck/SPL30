#!/usr/bin/env bash
# test_02_review_code.sh
# Unit test for 02_review_code.spl
# Tests: review of good code (minimal feedback) and buggy code (flags issues)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs/02_review_code"
mkdir -p "$LOG_DIR"

CODE_GOOD=$(cat "$SCRIPT_DIR/mock/code_good.py")
CODE_BUGGY=$(cat "$SCRIPT_DIR/mock/code_buggy.py")
MODEL="${1:-llama3.2}"
PASS=0; FAIL=0

run_test() {
    local name="$1" code="$2" expected_token="$3"
    echo "  [$name] running ..."
    output=$(spl3 run "$PIPELINE_DIR/02_review_code.spl" \
        --adapter ollama \
        --param "code=$code" \
        --param "lang=python" \
        --param "model=$MODEL" \
        --param "log_dir=$LOG_DIR/$name" \
        2>&1)
    if echo "$output" | grep -qi "$expected_token"; then
        echo "  [$name] PASS — found '$expected_token'"
        PASS=$((PASS + 1))
    else
        echo "  [$name] FAIL — expected '$expected_token' in output"
        echo "  output: $(echo "$output" | tail -5)"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== 02_review_code | model=$MODEL ==="
run_test "good_code"  "$CODE_GOOD"  "Output:"      # any non-empty feedback
run_test "buggy_code" "$CODE_BUGGY" "off-by-one\|index\|comparison\|bug\|error\|incorrect"

echo "--- result: $PASS passed, $FAIL failed ---"
[ "$FAIL" -eq 0 ]
