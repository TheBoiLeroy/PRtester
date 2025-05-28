from typing import List


def calculate_products(nums: List[int]) -> List[int]:
    """
    Calculate a list where each element at index i is the product of all numbers in the original list except the one at i.

    Args:
        nums (List[int]): A list of integers.

    Returns:
        List[int]: A list where each element is the product of all numbers except the one at the same index.

    Example:
        >>> calculate_products([1, 2, 3, 4])
        [24, 12, 8, 6]
    """
    n = len(nums)
    result = [1] * n
    
    # Left products
    left = 1
    for i in range(n):
        result[i] *= left
        left *= nums[i]
    
    # Right products
    right = 1
    for i in range(n-1, -1, -1):
        result[i] *= right
        right *= nums[i]
    
    return result


# Example usage
if __name__ == "__main__":
    print(calculate_products([1, 2, 3, 4]))  # Output: [24, 12, 8, 6]
    print(calculate_products([2, 3, 4, 5]))  # Output: [60, 40, 30, 24]