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
