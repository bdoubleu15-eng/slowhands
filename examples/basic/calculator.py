#!/usr/bin/env python3
"""
Basic Add-Only Calculator

A simple calculator that only performs addition with a maximum limit of 100,000.
This example demonstrates fundamental Python concepts: functions, loops, error handling.

Usage:
    python calculator.py              # Run demo
    python calculator.py --interactive  # Interactive mode
"""

LIMIT = 100000


def add(a: float, b: float) -> float:
    """
    Add two numbers together with limit checking.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
        
    Raises:
        ValueError: If any number or the result exceeds 100,000
    """
    if abs(a) > LIMIT:
        raise ValueError(f"Number {a:,} exceeds the limit of {LIMIT:,}")
    if abs(b) > LIMIT:
        raise ValueError(f"Number {b:,} exceeds the limit of {LIMIT:,}")
    
    result = a + b
    
    if abs(result) > LIMIT:
        raise ValueError(f"Result {result:,} exceeds the limit of {LIMIT:,}")
    
    return result


def add_many(*numbers: float) -> float:
    """
    Add multiple numbers together with limit checking.
    
    Args:
        *numbers: Variable number of arguments to add
    
    Returns:
        Sum of all numbers
    
    Raises:
        ValueError: If any number or total exceeds 100,000
    """
    total = 0.0
    
    for i, num in enumerate(numbers, 1):
        if abs(num) > LIMIT:
            raise ValueError(f"Number {num:,} at position {i} exceeds the limit of {LIMIT:,}")
        total += num
        if abs(total) > LIMIT:
            raise ValueError(f"Running total {total:,} exceeds the limit of {LIMIT:,}")
    
    return total


def interactive():
    """Run an interactive add-only calculator session."""
    print("=" * 50)
    print("ADD-ONLY CALCULATOR")
    print("Maximum value: 100,000")
    print("Commands: '=' to show total, 'c' to clear, 'q' to quit")
    print("=" * 50)
    
    total = 0.0
    
    while True:
        try:
            user_input = input(f"\nTotal: {total:,.2f} | Enter number: ").strip()
            
            if user_input.lower() == 'q':
                print(f"\nFinal total: {total:,.2f}")
                print("Goodbye!")
                break
            elif user_input.lower() == 'c':
                total = 0.0
                print("Calculator cleared.")
                continue
            elif user_input == '=':
                print(f"Current total: {total:,.2f}")
                continue
            
            num = float(user_input)
            
            if abs(num) > LIMIT:
                print(f"Error: {num:,} exceeds the limit of {LIMIT:,}")
                continue
            
            new_total = total + num
            if abs(new_total) > LIMIT:
                print(f"Error: Adding {num:,} would exceed the limit")
                continue
            
            total = new_total
            print(f"Added {num:,.2f}")
            
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print(f"\n\nFinal total: {total:,.2f}")
            break


def demo():
    """Demonstrate the calculator with examples."""
    print("ADD-ONLY CALCULATOR DEMO")
    print("=" * 50)
    
    examples = [
        ("Simple addition", lambda: add(5000, 3000)),
        ("Multiple numbers", lambda: add_many(10000, 20000, 30000, 15000)),
        ("With negatives", lambda: add(-25000, 75000)),
        ("At limit", lambda: add(50000, 50000)),
    ]
    
    for name, func in examples:
        try:
            result = func()
            print(f"{name}: {result:,.2f}")
        except ValueError as e:
            print(f"{name}: Error - {e}")
    
    print("\n" + "=" * 50)
    print("Error case: Exceeding limit")
    try:
        add(80000, 30000)
    except ValueError as e:
        print(f"Caught expected error: {e}")


if __name__ == "__main__":
    import sys
    
    if "--interactive" in sys.argv or "-i" in sys.argv:
        interactive()
    else:
        demo()
