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

Output:
[PASSED]

The code meets all the requirements specified, handling edge cases correctly and implementing a correct binary search algorithm.