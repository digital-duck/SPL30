[READY]
This specification provides sufficient detail for generating Python code for a binary search algorithm.

STRUCTURED SPEC:
1.  The function `binary_search` must be implemented in Python.
2.  The function must accept a single argument: `arr`, a list of integers.
3.  The function must accept a second argument: `target`, an integer representing the value to search for.
4.  The `arr` argument must be assumed to be a sorted list of integers in ascending order.
5.  The function must return the index of the `target` value within the `arr` list if the `target` is found.
6.  If the `target` value is not found within the `arr` list, the function must return -1.
7.  The implementation must utilize an iterative approach to the binary search algorithm.
8.  The iterative binary search algorithm must achieve a time complexity of O(log n), where n is the length of the input list `arr`.