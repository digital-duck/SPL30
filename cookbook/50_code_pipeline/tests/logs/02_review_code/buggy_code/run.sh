#!/usr/bin/env bash

CODE=$(cat <<'__SPL_PARAM_EOF__'
def binary_search(arr, target):
    """Buggy: ignores empty list, off-by-one on hi, wrong comparison direction."""
    lo, hi = 0, len(arr)        # bug: hi should be len(arr) - 1
    while lo < hi:              # bug: should be lo <= hi
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] > target: # bug: flipped comparison
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
__SPL_PARAM_EOF__
)

spl3 run /home/gong-mini/projects/digital-duck/SPL30/cookbook/56_code_pipeline/02_review_code.spl \
    --adapter ollama \
    --param "code=$CODE" \
    --param "lang=python" \
    --param "model=llama3.2" \
    --param "log_dir=/home/gong-mini/projects/digital-duck/SPL30/cookbook/56_code_pipeline/tests/logs/02_review_code/buggy_code" 
