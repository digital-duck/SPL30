#!/usr/bin/env bash
# test_03_improve_code.sh
# Unit test for 03_improve_code.spl
# Tests: improved code incorporates feedback and fixes known bugs

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs/03_improve_code"
mkdir -p "$LOG_DIR"

CODE_BUGGY=$(cat "$SCRIPT_DIR/mock/code_buggy.py")
FEEDBACK=$(cat "$SCRIPT_DIR/mock/feedback.txt")
MODEL="${1:-llama3.2}"
PASS=0; FAIL=0

run_test() {
    local name="$1" code="$2" feedback="$3" expected_token="$4"
    echo "  [$name] running ..."
    output=$(spl3 run "$PIPELINE_DIR/03_improve_code.spl" \
        --adapter ollama \
        --param "code=$code" \
        --param "feedback=$feedback" \
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

echo "=== 03_improve_code | model=$MODEL ==="
run_test "fix_buggy" "$CODE_BUGGY" "$FEEDBACK" "def binary_search"

echo "--- result: $PASS passed, $FAIL failed ---"
[ "$FAIL" -eq 0 ]
