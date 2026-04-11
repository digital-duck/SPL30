#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/targets/python/langgraph"
TASK="What are the benefits of meditation?"
MAX_ITERATIONS=3
MODELS=(
    # "llama3.2"
    "gemma3"
    "gemma4:e2b"
    "gemma4:e4b"
)

for MODEL in "${MODELS[@]}"; do
    # Sanitize model name for directory (replace : with _)
    SAFE_MODEL="${MODEL//:/_}"
    LOG_DIR="$TARGET/logs-$SAFE_MODEL"
    mkdir -p "$LOG_DIR"

    echo "=========================================="
    echo "Running with model: $MODEL"
    echo "Log dir: $LOG_DIR"
    echo "=========================================="

    python "$TARGET/self_refine_langgraph.py" \
        --task "$TASK" \
        --max-iterations "$MAX_ITERATIONS" \
        --writer-model "$MODEL" \
        --critic-model "$MODEL" \
        --log-dir "$LOG_DIR"

    echo "Done: $MODEL"
    echo ""
done

echo "All models completed."
