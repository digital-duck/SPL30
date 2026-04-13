#!/usr/bin/env bash

spl3 run /home/gong-mini/projects/digital-duck/SPL30/cookbook/56_code_pipeline/07_spec_judge.spl \
    --adapter ollama \
    --param "spec=Write a Python function `binary_search(arr, target)` that searches a sorted list for a target value. Return the index if found, or -1 if not found. Handle edge cases: empty list, single element, duplicates (return any matching index)." \
    --param "out_spec=Write a Python function `binary_search(arr, target)` that performs binary search on a sorted list. Returns the index of target if found, or -1 if not present. Handles empty input gracefully." \
    --param "model=llama3.2" \
    --param "log_dir=/home/gong-mini/projects/digital-duck/SPL30/cookbook/56_code_pipeline/tests/logs/07_spec_judge/closed_path" 
