#!/usr/bin/env bash
# benchmark-1.sh — self_refine benchmark across local Ollama models
# Usage: bash cookbook/05_self_refine/benchmark-1.sh
# Run from the SPL30 repo root.

set -euo pipefail

MODELS=(
    "llama3.2"
    "gemma3"
    "gemma4:e2b"
    "gemma4:e4b"
)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPL_FILE="$SCRIPT_DIR/self_refine.spl"

for MODEL in "${MODELS[@]}"; do
    # Sanitize model name for use in directory/file names (replace : with -)
    MODEL_SLUG="${MODEL//:/-}"
    LOG_DIR="$SCRIPT_DIR/logs-spl-ollama-${MODEL_SLUG}"

    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  Model: $MODEL"
    echo "  Logs:  $LOG_DIR"
    echo "════════════════════════════════════════════════════════════"

    mkdir -p "$LOG_DIR"

    spl3 run "$SPL_FILE" \
        --adapter ollama \
        --model "$MODEL" \
        --param writer_model="$MODEL" \
        --param critic_model="$MODEL" \
        --log-prompts "$LOG_DIR" \
        --param log_dir="$LOG_DIR" \
        2>&1 | tee "$LOG_DIR/run-$(date +%Y%m%d-%H%M%S).log"

    echo ""
    echo "  Done: $MODEL"
done

echo ""
echo "All models complete."
