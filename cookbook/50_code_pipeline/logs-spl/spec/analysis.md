```python
def binary_search(arr, target):
  """
  Performs a binary search on a sorted array to find the index of a target value.

  Args:
    arr: A sorted array of integers.
    target: The integer value to search for.

  Returns:
    The index of the target value in the array if found, otherwise -1.
  """

  low = 0
  high = len(arr) - 1

  while low <= high:
    mid = (low + high) // 2  # Integer division to find the middle index

    if arr[mid] == target:
      return mid  # Target found at index mid
    elif arr[mid] < target:
      low = mid + 1  # Target is in the right half
    else:
      high = mid - 1  # Target is in the left half

  return -1  # Target not found in the array
```

**Explanation:**

1. **Initialization:**
   - `low`:  Index of the first element in the search space (initially 0).
   - `high`: Index of the last element in the search space (initially `len(arr) - 1`).

2. **Iteration (while loop):**
   - The loop continues as long as `low` is less than or equal to `high`.  This means there's still a portion of the array to search.

3. **Calculate Middle Index:**
   - `mid = (low + high) // 2`:  Calculates the middle index of the current search space.  Integer division (`//`) ensures that `mid` is an integer.

4. **Comparison:**
   - `if arr[mid] == target:`: If the value at the middle index is equal to the target, we've found it, so return `mid`.
   - `elif arr[mid] < target:`: If the value at the middle index is less than the target, it means the target (if it exists) must be in the right half of the array.  So, we update `low` to `mid + 1` to narrow the search space.
   - `else:`: If the value at the middle index is greater than the target, it means the target (if it exists) must be in the left half of