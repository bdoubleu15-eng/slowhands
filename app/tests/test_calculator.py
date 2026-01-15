#!/usr/bin/env python3
"""
Test script for the add-only calculator
"""

def test_add_function():
    """Test the add_numbers function from calculator.py"""
    # Import the function
    import calculator
    
    test_cases = [
        {
            "name": "Simple addition",
            "numbers": [10, 20, 30],
            "expected": 60
        },
        {
            "name": "Negative numbers",
            "numbers": [100, -50, 25],
            "expected": 75
        },
        {
            "name": "Decimal numbers",
            "numbers": [10.5, 20.3, 5.2],
            "expected": 36.0
        },
        {
            "name": "Large numbers within limit",
            "numbers": [50000, 40000, 10000],
            "expected": 100000
        },
        {
            "name": "Zero addition",
            "numbers": [0, 0, 0],
            "expected": 0
        }
    ]
    
    print("Testing add_numbers function:")
    print("=" * 50)
    
    for test in test_cases:
        try:
            result = calculator.add_numbers(test["numbers"])
            status = "✓ PASS" if result == test["expected"] else "✗ FAIL"
            print(f"{status} {test['name']}: {test['numbers']} = {result}")
        except ValueError as e:
            print(f"✗ FAIL {test['name']}: {e}")
    
    print("\nTesting limits (should fail):")
    print("=" * 50)
    
    limit_tests = [
        {
            "name": "Number exceeds 100,000",
            "numbers": [100001, 10]
        },
        {
            "name": "Negative exceeds -100,000",
            "numbers": [-100001, 10]
        },
        {
            "name": "Total exceeds 100,000",
            "numbers": [50000, 50001]
        }
    ]
    
    for test in limit_tests:
        try:
            result = calculator.add_numbers(test["numbers"])
            print(f"✗ FAIL {test['name']}: Expected error but got {result}")
        except ValueError as e:
            print(f"✓ PASS {test['name']}: {e}")

def run_simple_calculator_demo():
    """Run a demo of the simple calculator"""
    print("\n" + "=" * 50)
    print("DEMO: Simple Calculator Usage")
    print("=" * 50)
    
    # Simulate user inputs
    print("Example session:")
    print("1. Enter: 10")
    print("2. Enter: 20")
    print("3. Enter: 30")
    print("4. Enter: = (to calculate)")
    print("\nExpected output: Total: 60")
    
    # Actually test it
    print("\n" + "=" * 50)
    print("Actual test:")
    
    # We'll simulate by calling the function directly
    import simple_calculator
    
    # Since we can't simulate user input easily in this test,
    # let's show how to use the calculator
    print("\nTo use the calculator:")
    print("1. Run: python simple_calculator.py")
    print("2. Enter numbers one by one")
    print("3. Type '=' to see the total")
    print("4. Type 'q' to quit")

if __name__ == "__main__":
    test_add_function()
    run_simple_calculator_demo()
    
    print("\n" + "=" * 50)
    print("QUICK START:")
    print("=" * 50)
    print("Run the interactive calculator:")
    print("  $ python simple_calculator.py")
    print("\nOr use the batch calculator:")
    print("  $ python calculator.py")
    print("\nTest the functionality:")
    print("  $ python test_calculator.py")