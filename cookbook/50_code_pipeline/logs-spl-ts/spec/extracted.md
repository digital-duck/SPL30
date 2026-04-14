## Specification: Binary Search Algorithm

**1. Purpose:**

This algorithm implements the binary search algorithm to efficiently locate a specific value (the “target”) within a sorted list of integers. The primary goal is to quickly determine if the target exists within the list and, if so, to return the index of its first occurrence.

**2. Inputs:**

*   `arr`: A sorted list of integers.  This list *must* be sorted in ascending order for the algorithm to function correctly. The list may be empty.
*   `target`: An integer value to search for within the list `arr`.

**3. Outputs:**

*   The algorithm returns a single integer representing the index of the `target` value within the list `arr`.
*   If the `target` value is not found within the list `arr`, the algorithm returns the integer value `-1`.

**4. Behaviour:**

The algorithm employs an iterative approach to search for the `target` within the sorted list. It works as follows:

1.  **Initialization:**
    *   It initializes two index variables, `low` and `high`, to represent the beginning and end of the search range within the list. `low` is initialized to 0 (the index of the first element), and `high` is initialized to `len(arr) - 1` (the index of the last element).
2.  **Iteration:**
    *   The algorithm enters a `while` loop that continues as long as the `low` index is less than or equal to the `high` index.
    *   Within the loop, it calculates the middle index, `mid`, as the average of `low` and `high`.
    *   It compares the value at the `mid` index (`arr[mid]`) with the `target` value.
        *   **If `arr[mid] == target`:** The `target` value has been found. The algorithm immediately returns the `mid` index.
        *   **If `arr[mid] < target`:** The `target` value must be located in the right half of the remaining search range. Therefore, the `low` index is updated to `mid + 1`, effectively discarding the left half of the range.
        *   **If `arr[mid] > target`:** The `target` value must be located in the left half of the remaining search range. Therefore, the `high` index is updated to `mid - 1`, effectively discarding the right half of the range.
3.  **Target Not Found:**
    *   If the `while` loop completes without finding the `target` value (i.e., `low` becomes greater than `high`), it means the `target` value is not present in the list. The algorithm returns the integer value `-1`.

**5. Assumptions:**

*   The input list `arr` is guaranteed to be sorted in ascending order before being passed to the algorithm.  If the list is not sorted, the algorithm's results will be unpredictable.
*   The `target` value is an integer. The algorithm is designed to work specifically with integer values.
*   The list `arr` can contain duplicate values of the target. The algorithm will return the index of the *first* occurrence of the target if it exists.
