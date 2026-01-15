#!/usr/bin/env python3
"""
Quick demonstration of the add-only calculator
"""

def demonstrate_calculator():
    """Show examples of calculator usage"""
    
    print("ADD-ONLY CALCULATOR DEMONSTRATION")
    print("=" * 50)
    
    examples = [
        ("Simple addition", [10, 20, 30], 60),
        ("With negative numbers", [100, -50, 25], 75),
        ("Decimal numbers", [10.5, 20.3, 5.2], 36.0),
        ("Maximum limit", [50000, 40000, 10000], 100000),
        ("Mixed types", [1000, -500, 250.5, 249.5], 1000),
    ]
    
    print("\nValid Examples:")
    print("-" * 30)
    
    for name, numbers, expected in examples:
        try:
            import calculator
            result = calculator.add_numbers(numbers)
            print(f"{name}:")
            print(f"  {numbers}")
            print(f"  Result: {result} {'✓' if result == expected else '✗'}")
            print()
        except ValueError as e:
            print(f"{name}: ERROR - {e}")
            print()
    
    print("\nInvalid Examples (should fail):")
    print("-" * 30)
    
    invalid_examples = [
        ("Number too large", [100001, 10]),
        ("Number too small", [-100001, 10]),
        ("Total too large", [50000, 50001]),
        ("Total too small", [-50000, -50001]),
    ]
    
    for name, numbers in invalid_examples:
        try:
            import calculator
            result = calculator.add_numbers(numbers)
            print(f"{name}:")
            print(f"  {numbers}")
            print(f"  UNEXPECTED SUCCESS: Got {result}")
            print()
        except ValueError as e:
            print(f"{name}:")
            print(f"  {numbers}")
            print(f"  Expected error: {e}")
            print()
    
    print("=" * 50)
    print("HOW TO USE:")
    print("=" * 50)
    print("1. For interactive use: python simple_calculator.py")
    print("2. For batch input: python calculator.py")
    print("3. To run tests: python test_calculator.py")
    print("4. To see this demo: python demo.py")

if __name__ == "__main__":
    demonstrate_calculator()