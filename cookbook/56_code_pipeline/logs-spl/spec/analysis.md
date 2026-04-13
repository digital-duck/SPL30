Okay, let's craft a binary search function in Python that fulfills the requirement of returning the index of a target value if found, or -1 if not.

```python
def binary_search(arr, target):
  """
  Performs a binary search on a sorted array to find the index of a target value.

  Args:
    arr: A sorted list or array of integers.
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


# Example Usage:
sorted_array = [2, 5, 7, 8, 11, 12]
target_value = 13

index = binary_search(sorted_array, target_value)

if index != -1:
  print(f"Target {target_value} found at index {index}")
else:
  print(f"Target {target_value} not found in the array")

target_value = 11
index = binary_search(sorted_array, target_value)

if index != -1:
  print(f"Target {target_value} found at index {index}")
else:
  print(f"Target {target_value} not found in the array")
```

**Explanation:**

1. **Initialization:**
   - `low`:  Index of the first element (0).
   - `high`: Index of the last element (length of array - 1).

2. **Iteration (while loop):**
   - The `while low <= high:` loop continues as long as the search space (defined by `low` and `high`) is not empty.

3. **Calculate Middle Index:**
   