#!/usr/bin/env bash

CODE=$(cat <<'__SPL_PARAM_EOF__'
def binary_search(arr, target):
    """Search a sorted list for target. Return index if found, -1 otherwise."""
    if not arr:
        return -1
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
__SPL_PARAM_EOF__
)

spl3 run /home/gong-mini/projects/digital-duck/SPL30/cookbook/56_code_pipeline/04_test_code.spl \
    --adapter ollama \
    --param "code=$CODE" \
    --param "spec=Write a Python function `binary_search(arr, target)` that searches a sorted list for a target value. Return the index if found, or -1 if not found. Handle edge cases: empty list, single element, duplicates (return any matching index)." \
    --param "lang=python" \
    --param "model=llama3.2" \
    --param "log_dir=/home/gong-mini/projects/digital-duck/SPL30/cookbook/56_code_pipeline/tests/logs/04_test_code/good_code" 
