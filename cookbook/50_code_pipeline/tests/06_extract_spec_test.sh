#!/usr/bin/env bash
# test_06_extract_spec.sh
# Unit test for 06_extract_spec.spl
# Tests: spec is reverse-engineered from code — output mentions binary search

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs/06_extract_spec"
mkdir -p "$LOG_DIR"

source "$SCRIPT_DIR/helpers.sh"

CODE=$(cat "$SCRIPT_DIR/mock/code_good.py")
MODEL="${1:-llama3.2}"
PASS=0; FAIL=0

run_test() {
    local name="$1" expected_token="$2"
    local run_script="$LOG_DIR/$name/run.sh"
    save_run_script "$run_script" "$PIPELINE_DIR/06_extract_spec.spl" ollama \
        code "$CODE" model "$MODEL" log_dir "$LOG_DIR/$name"
    local -a cmd=(spl3 run "$PIPELINE_DIR/06_extract_spec.spl"
        --adapter ollama
        --param "code=$CODE"
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

echo "=== 06_extract_spec | model=$MODEL ==="
run_test "extract_from_code" "binary\|search\|sorted\|index"

echo "--- result: $PASS passed, $FAIL failed ---"
[ "$FAIL" -eq 0 ]
