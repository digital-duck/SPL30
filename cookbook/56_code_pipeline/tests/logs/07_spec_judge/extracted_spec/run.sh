#!/usr/bin/env bash

OUT_SPEC=$(cat <<'__SPL_PARAM_EOF__'
**Binary Search Specification**

**Purpose:**
The binary search function solves the problem of finding a target element in a sorted list. It returns the index of the target element if found, indicating its position in the list; otherwise, it returns -1 to indicate that the target element is not present.

**Inputs:**

* `arr`: A sorted list of elements (of an unspecified type that can be compared using `<` or `>` operators).
* `target`: The element to search for in the list.
* The input list `arr` must be non-empty (`len(arr) > 0`). If the list is empty, the function returns -1.

**Outputs:**

* An integer representing the index of the target element in the list if found; otherwise, -1.

**Behaviour:**

1. The search starts by checking if the input list `arr` is non-empty. If it's not, the function immediately returns -1.
2. The algorithm then iterates until the midpoint `mid` of the range defined by `lo` and `hi` exceeds the length of the list (`lo > hi`). This is because a sorted list with an odd number of elements cannot be split into two equal halves.
3. At each iteration, the function compares the middle element of the current range (`arr[mid]`) to the target element (`target`):
	* If they match, the function returns the index `mid`.
	* If `arr[mid]` is less than `target`, the search space is narrowed down to the right half of the list by setting `lo = mid + 1`.
	* If `arr[mid]` is greater than `target`, the search space is narrowed down to the left half of the list by setting `hi = mid - 1`.
4. When the loop finishes, and the target element has not been found in the entire range, the function returns -1.

**Assumptions:**

* The input list `arr` is sorted in ascending or descending order.
* The elements in the list can be compared using the `<` or `>` operators.
* The target element exists in the list if it's present at all.
__SPL_PARAM_EOF__
)

spl3 run /home/gong-mini/projects/digital-duck/SPL30/cookbook/56_code_pipeline/07_spec_judge.spl \
    --adapter ollama \
    --param "spec=Write a Python function `binary_search(arr, target)` that searches a sorted list for a target value. Return the index if found, or -1 if not found. Handle edge cases: empty list, single element, duplicates (return any matching index)." \
    --param "out_spec=$OUT_SPEC" \
    --param "model=llama3.2" \
    --param "log_dir=/home/gong-mini/projects/digital-duck/SPL30/cookbook/56_code_pipeline/tests/logs/07_spec_judge/extracted_spec" 
