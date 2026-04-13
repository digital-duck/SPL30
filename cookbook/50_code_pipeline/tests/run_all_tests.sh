#!/usr/bin/env bash
# run_all_tests.sh
# Run all unit tests for cookbook/56_code_pipeline sub-workflows sequentially.
# Usage: bash run_all_tests.sh [model]
#   model: Ollama model to use (default: llama3.2)
#
# Unit tests run fastest with a small model (llama3.2).
# For higher-confidence results use gemma3 or gemma4:e2b.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:-llama3.2}"

TESTS=(
    00_analyze_spec_test.sh
    01_generate_code_test.sh
    02_review_code_test.sh
    03_improve_code_test.sh
    04_test_code_test.sh
    05_document_code_test.sh
    06_extract_spec_test.sh
    07_spec_judge_test.sh
)

TOTAL_PASS=0
TOTAL_FAIL=0
FAILED_TESTS=()

echo "========================================"
echo "  code_pipeline unit tests | model=$MODEL"
echo "========================================"
echo ""

for TEST in "${TESTS[@]}"; do
    echo ">>> $TEST"
    if bash "$SCRIPT_DIR/$TEST" "$MODEL"; then
        TOTAL_PASS=$((TOTAL_PASS + 1))
    else
        TOTAL_FAIL=$((TOTAL_FAIL + 1))
        FAILED_TESTS+=("$TEST")
    fi
    echo ""
done

echo "========================================"
echo "  SUMMARY: $TOTAL_PASS passed, $TOTAL_FAIL failed"
if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo "  FAILED:"
    for t in "${FAILED_TESTS[@]}"; do echo "    - $t"; done
fi
echo "========================================"

[ "$TOTAL_FAIL" -eq 0 ]
