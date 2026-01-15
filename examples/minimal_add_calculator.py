#!/usr/bin/env python3
"""
Minimal Add-Only Calculator
The simplest possible add-only calculator
"""

def add(*args):
    """
    Add any number of values together.
    
    Usage:
        add(1, 2, 3) -> 6
        add(10, 20) -> 30
        add(5) -> 5
        add() -> 0
    """
    return sum(args)

# Example usage
if __name__ == "__main__":
    print("Minimal Add-Only Calculator")
    print("=" * 30)
    
    # Examples
    print(f"add(1, 2, 3) = {add(1, 2, 3)}")
    print(f"add(10, 20) = {add(10, 20)}")
    print(f"add(5) = {add(5)}")
    print(f"add() = {add()}")
    print(f"add(2.5, 3.5) = {add(2.5, 3.5)}")
    print(f"add(-1, 0, 1) = {add(-1, 0, 1)}")