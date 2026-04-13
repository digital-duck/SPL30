```python
def binary_search(arr, target):
    """
    Performs a binary search on a sorted array to find the index of a target value.

    Args:
        arr: A sorted list of numbers.
        target: The value to search for.

    Returns:
        The index of the target value in the array if found, otherwise -1.

    Raises:
        TypeError: If 'arr' is not a list or if elements in 'arr' are not comparable.
        ValueError: If 'arr' is not sorted.
    """
    # Input Validation
    if not isinstance(arr, list):
        raise TypeError("Input 'arr' must be a list.")

    # Check if elements are comparable (basic type check)
    try:
        # Attempt a comparison to ensure elements are comparable
        arr[0] < arr[1]  # This will raise TypeError if elements can't be compared
    except TypeError:
        raise TypeError("Elements in 'arr' must be comparable (e.g., numbers).")

    # Check if the array is sorted
    if any(arr[i] > arr[i+1] for i in range(len(arr)-1)):
        raise ValueError("Input 'arr' must be a sorted list.")

    low = 0
    high = len(arr) - 1

    while low <= high:
        mid = (low + high) // 2

        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1

    return -1



# Example Usage and Test Cases
if __name__ == '__main__':
    # Test Cases
    arr1 = [2, 5, 7, 8, 11, 12]
    target1 = 13
    target2 = 12
    target3 = 2
    target4 = 12
    target5 = 5
    target6 = -5

    print(f"Index of {target1}: {binary_search(arr1, target1)}")  # Output: -1
    print(f"Index of {target2}: {binary_search(arr1, target2)}")  # Output: 5
    print(f"Index of {target3}: {binary_search(arr1, target3)}")  # Output: 0
    print(f"Index of {target4}: {binary_search(arr1, target4)}")  # Output: 5
    print(f"Index of {target5}: {binary_search(arr1, target5)}")  # Output: 1
    print(f"Index of {target6}: {binary_search(arr1, target6)}")  # Output: -1

    # Test with an empty array
    arr_empty = []
    target_empty = 5
    print(f"Index of {target_empty} in empty array: {binary_search(arr_empty, target_empty)}") # Output: -1

    # Test with negative numbers
    arr_neg = [-5, -2, 0, 3]
    target_neg = -2
    print(f"Index of {target_neg} in negative array: {binary_search(arr_neg, target_neg)}") # Output: 1

    # Test for invalid input (unsorted array)
    try:
        binary_search([5, 2, 8, 1], 8)
    except ValueError as e:
        print(f"Caught expected ValueError: {e}")  # Output: Caught expected ValueError: Input 'arr' must be a sorted list.

    # Test for invalid input (non-list)
    try:
        binary_search("not a list", 8)
    except TypeError as e:
        print(f"Caught expected TypeError: {e}") # Output: Caught expected TypeError: Input 'arr' must be a list.

    # Test for non-comparable elements
    try:
        binary_search([1, "a", 3], 3)
    except TypeError as e:
        print(f"Caught expected TypeError: {e}")  # Output: Caught expected TypeError: Elements in 'arr' must be comparable (e.g., numbers).
```