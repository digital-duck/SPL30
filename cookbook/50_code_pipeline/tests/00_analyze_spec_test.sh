#!/usr/bin/env bash
# test_00_analyze_spec.sh
# Unit test for 00_analyze_spec.spl
# Tests: READY path (clear spec) and VAGUE path (vague spec)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs/00_analyze_spec"
mkdir -p "$LOG_DIR"

source "$SCRIPT_DIR/helpers.sh"

SPEC_CLEAR=$(cat "$SCRIPT_DIR/mock/spec_clear.txt")
SPEC_VAGUE=$(cat "$SCRIPT_DIR/mock/spec_vague.txt")
MODEL="${1:-llama3.2}"
PASS=0; FAIL=0

run_test() {
    local name="$1" spec="$2" expected_token="$3"
    local run_script="$LOG_DIR/$name/run.sh"
    save_run_script "$run_script" "$PIPELINE_DIR/00_analyze_spec.spl" ollama \
        spec "$spec" model "$MODEL" log_dir "$LOG_DIR/$name"
    local -a cmd=(spl3 run "$PIPELINE_DIR/00_analyze_spec.spl"
        --adapter ollama
        --param "spec=$spec"
        --param "model=$MODEL"
        --param "log_dir=$LOG_DIR/$name")
    echo "  [$name] running ..."
    echo "  CMD: ${cmd[*]}"
    echo "  RUN: $run_script"
    output=$("${cmd[@]}" 2>&1)
    if echo "$output" | grep -q "$expected_token"; then
        echo "  [$name] PASS — found '$expected_token'"
        PASS=$((PASS + 1))
    else
        echo "  [$name] FAIL — expected '$expected_token' in output"
        echo "  output: $(echo "$output" | tail -5)"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== 00_analyze_spec | model=$MODEL ==="
run_test "clear_spec" "$SPEC_CLEAR" "[READY]"
run_test "vague_spec" "$SPEC_VAGUE" "[VAGUE]"

echo "--- result: $PASS passed, $FAIL failed ---"
[ "$FAIL" -eq 0 ]
