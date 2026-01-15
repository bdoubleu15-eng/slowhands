#!/usr/bin/env python3
"""
Simple command-line calculator
Usage: python simple_calc.py <num1> <operation> <num2>
Operations: +, -, *, /
"""

import sys

def calculate(num1, operation, num2):
    """Perform calculation based on operation"""
    if operation == '+':
        return num1 + num2
    elif operation == '-':
        return num1 - num2
    elif operation == '*':
        return num1 * num2
    elif operation == '/':
        if num2 == 0:
            raise ValueError("Cannot divide by zero!")
        return num1 / num2
    else:
        raise ValueError(f"Invalid operation: {operation}")

def main():
    if len(sys.argv) != 4:
        print("Usage: python simple_calc.py <num1> <operation> <num2>")
        print("Operations: +, -, *, /")
        print("Example: python simple_calc.py 5 + 3")
        return
    
    try:
        num1 = float(sys.argv[1])
        operation = sys.argv[2]
        num2 = float(sys.argv[3])
        
        result = calculate(num1, operation, num2)
        print(f"{num1} {operation} {num2} = {result}")
        
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()