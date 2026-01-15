#!/usr/bin/env python3
"""
Advanced Calculator with more operations
"""

import math

def show_menu():
    """Display the calculator menu"""
    print("\n" + "=" * 50)
    print("ADVANCED CALCULATOR")
    print("=" * 50)
    print("\nBasic Operations:")
    print("  1. Addition (+)")
    print("  2. Subtraction (-)")
    print("  3. Multiplication (*)")
    print("  4. Division (/)")
    print("  5. Modulus (%)")
    print("  6. Exponentiation (^)")
    
    print("\nAdvanced Operations:")
    print("  7. Square root (√)")
    print("  8. Power (x^y)")
    print("  9. Logarithm (log)")
    print("  10. Sine (sin)")
    print("  11. Cosine (cos)")
    print("  12. Tangent (tan)")
    
    print("\nOther:")
    print("  13. Clear memory")
    print("  14. Show memory")
    print("  15. Exit")
    print("-" * 50)

def main():
    memory = 0  # Simple memory storage
    
    print("Welcome to Advanced Calculator!")
    print("Type 'help' for menu or 'exit' to quit")
    
    while True:
        try:
            command = input("\ncalc> ").strip().lower()
            
            if command in ['exit', 'quit', 'q']:
                print("Goodbye!")
                break
            elif command in ['help', 'h', 'menu']:
                show_menu()
                continue
            elif command == 'clear':
                memory = 0
                print("Memory cleared")
                continue
            elif command == 'mem':
                print(f"Memory: {memory}")
                continue
            
            # Try to evaluate as expression
            try:
                # Replace common symbols
                expr = command.replace('^', '**').replace('√', 'math.sqrt')
                
                # Handle special functions
                if 'sin(' in expr:
                    expr = expr.replace('sin(', 'math.sin(')
                if 'cos(' in expr:
                    expr = expr.replace('cos(', 'math.cos(')
                if 'tan(' in expr:
                    expr = expr.replace('tan(', 'math.tan(')
                if 'log(' in expr:
                    expr = expr.replace('log(', 'math.log10(')
                if 'ln(' in expr:
                    expr = expr.replace('ln(', 'math.log(')
                
                # Evaluate the expression
                result = eval(expr, {"__builtins__": {}}, {"math": math, "mem": memory})
                
                # Store in memory
                memory = result
                print(f"Result: {result}")
                
            except Exception as e:
                print(f"Error: {e}")
                print("Try: 5 + 3, 2^3, sqrt(16), sin(0), log(100)")
                
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()