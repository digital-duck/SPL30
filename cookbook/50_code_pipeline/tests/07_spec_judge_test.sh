#!/usr/bin/env bash
# test_07_spec_judge.sh
# Unit test for 07_spec_judge.spl
# Tests: CLOSED path (matching specs) and DIVERGED path (mismatched specs)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs/07_spec_judge"
mkdir -p "$LOG_DIR"

source "$SCRIPT_DIR/helpers.sh"

SPEC_ORIG=$(cat "$SCRIPT_DIR/mock/spec_clear.txt")
SPEC_MATCHING=$(cat "$SCRIPT_DIR/mock/spec_extracted.txt")         # close paraphrase → CLOSED
SPEC_EXTRACTED=$(cat "$SCRIPT_DIR/mock/extracted_bin_search.md")   # actual step-06 output → real NDD closure test
SPEC_DIVERGED="Write a sorting algorithm that sorts a list of integers in ascending order using bubble sort."

MODEL="${1:-llama3.2}"
PASS=0; FAIL=0

run_test() {
    local name="$1" spec="$2" out_spec="$3" expected_token="$4"
    local run_script="$LOG_DIR/$name/run.sh"
    save_run_script "$run_script" "$PIPELINE_DIR/07_spec_judge.spl" ollama \
        spec "$spec" out_spec "$out_spec" model "$MODEL" log_dir "$LOG_DIR/$name"
    local -a cmd=(spl3 run "$PIPELINE_DIR/07_spec_judge.spl"
        --adapter ollama
        --param "spec=$spec"
        --param "out_spec=$out_spec"
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

echo "=== 07_spec_judge | model=$MODEL ==="
run_test "closed_path"    "$SPEC_ORIG" "$SPEC_MATCHING"   "[CLOSED]"
run_test "diverged_path"  "$SPEC_ORIG" "$SPEC_DIVERGED"   "[DIVERGED]"
run_test "extracted_spec" "$SPEC_ORIG" "$SPEC_EXTRACTED"  "[CLOSED]\|[DIVERGED]"   # real NDD closure — no expected verdict

echo "--- result: $PASS passed, $FAIL failed ---"
[ "$FAIL" -eq 0 ]
