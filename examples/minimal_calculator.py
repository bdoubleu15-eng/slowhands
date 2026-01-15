#!/usr/bin/env python3
"""
Minimal Add-Only Calculator
Adds numbers up to 100,000
"""

def add_only_calculator(*numbers):
    """
    Add numbers together with a limit of 100,000.
    
    Args:
        *numbers: Variable number of arguments to add
    
    Returns:
        Sum of the numbers
    
    Raises:
        ValueError: If any number or total exceeds 100,000
    """
    LIMIT = 100000
    total = 0
    
    for i, num in enumerate(numbers, 1):
        if abs(num) > LIMIT:
            raise ValueError(f"Number {num} exceeds the limit of {LIMIT}")
        total += num
    
    if abs(total) > LIMIT:
        raise ValueError(f"Total {total} exceeds the limit of {LIMIT}")
    
    return total

# Example usage
if __name__ == "__main__":
    # Example 1: Simple addition
    print("Example 1: 10 + 20 + 30")
    print(f"Result: {add_only_calculator(10, 20, 30)}")
    print()
    
    # Example 2: Larger numbers
    print("Example 2: 50000 + 30000 + 20000")
    print(f"Result: {add_only_calculator(50000, 30000, 20000)}")
    print()
    
    # Example 3: With negative numbers
    print("Example 3: 75000 + (-25000)")
    print(f"Result: {add_only_calculator(75000, -25000)}")
    print()
    
    # Example 4: Error case
    print("Example 4: 100001 + 10 (should error)")
    try:
        result = add_only_calculator(100001, 10)
        print(f"Result: {result}")
    except ValueError as e:
        print(f"Error: {e}")