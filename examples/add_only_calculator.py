#!/usr/bin/env python3
"""
Simple Add-Only Calculator
A minimal calculator that only performs addition
"""

def add_numbers(a, b):
    """
    Add two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    return a + b

def add_multiple_numbers(numbers):
    """
    Add multiple numbers together.
    
    Args:
        numbers: List of numbers to add
        
    Returns:
        Sum of all numbers
    """
    total = 0
    for num in numbers:
        total += num
    return total

def main():
    """Simple demonstration of the add-only calculator."""
    print("Add-Only Calculator Demo")
    print("=" * 30)
    
    # Example 1: Add two numbers
    print("\nExample 1: Adding two numbers")
    result1 = add_numbers(5, 3)
    print(f"5 + 3 = {result1}")
    
    # Example 2: Add multiple numbers
    print("\nExample 2: Adding multiple numbers")
    numbers = [1, 2, 3, 4, 5]
    result2 = add_multiple_numbers(numbers)
    print(f"{' + '.join(str(n) for n in numbers)} = {result2}")
    
    # Example 3: Interactive addition
    print("\nExample 3: Interactive addition")
    try:
        num1 = float(input("Enter first number: "))
        num2 = float(input("Enter second number: "))
        result3 = add_numbers(num1, num2)
        print(f"{num1} + {num2} = {result3}")
    except ValueError:
        print("Please enter valid numbers!")

if __name__ == "__main__":
    main()