#!/usr/bin/env bash
# test_01_generate_code.sh
# Unit test for 01_generate_code.spl
# Tests: code is generated (non-empty), contains function definition

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs/01_generate_code"
mkdir -p "$LOG_DIR"

source "$SCRIPT_DIR/helpers.sh"

SPEC=$(cat "$SCRIPT_DIR/mock/spec_clear.txt")
MODEL="${1:-llama3.2}"
PASS=0; FAIL=0

lang_ext() {
    case "$1" in
        go)   echo "go"   ;;
        ts)   echo "ts"   ;;
        js)   echo "js"   ;;
        java) echo "java" ;;
        rust) echo "rs"   ;;
        *)    echo "py"   ;;
    esac
}

run_test() {
    local name="$1" lang="$2" expected_token="$3"
    local ext; ext=$(lang_ext "$lang")
    local code_file="$LOG_DIR/$name/target/$lang/code.$ext"
    local run_script="$LOG_DIR/$name/run.sh"
    save_run_script "$run_script" "$PIPELINE_DIR/01_generate_code.spl" ollama \
        spec "$SPEC" lang "$lang" model "$MODEL" log_dir "$LOG_DIR/$name"
    local -a cmd=(spl3 run "$PIPELINE_DIR/01_generate_code.spl"
        --adapter ollama
        --param "spec=$SPEC"
        --param "lang=$lang"
        --param "model=$MODEL"
        --param "log_dir=$LOG_DIR/$name")
    echo "  [$name] running ..."
    echo "  CMD: ${cmd[*]}"
    echo "  RUN: $run_script"
    output=$("${cmd[@]}" 2>&1)
    if echo "$output" | grep -qi "$expected_token"; then
        echo "  [$name] PASS — found '$expected_token' in output"
        PASS=$((PASS + 1))
    else
        echo "  [$name] FAIL — expected '$expected_token' in output"
        echo "  output: $(echo "$output" | tail -5)"
        FAIL=$((FAIL + 1))
    fi
    if [ -f "$code_file" ]; then
        echo "  [$name] PASS — artifact written: $code_file"
        PASS=$((PASS + 1))
    else
        echo "  [$name] FAIL — artifact missing: $code_file"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== 01_generate_code | model=$MODEL ==="
run_test "python" "python" "def binary_search"
run_test "go"     "go"     "func binary"

echo "--- result: $PASS passed, $FAIL failed ---"
[ "$FAIL" -eq 0 ]
