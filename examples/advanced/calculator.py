#!/usr/bin/env python3
"""
Advanced Calculator

A full-featured calculator supporting basic arithmetic, trigonometry, and logarithms.
This example demonstrates expression evaluation, error handling, and math operations.

Usage:
    python calculator.py              # Interactive mode
    
Commands:
    Enter mathematical expressions like: 5 + 3, 2^3, sqrt(16), sin(0), log(100)
    Type 'help' for menu, 'mem' to see memory, 'clear' to reset memory, 'exit' to quit
"""

import math


def show_help():
    """Display the calculator help menu."""
    print("\n" + "=" * 50)
    print("ADVANCED CALCULATOR - HELP")
    print("=" * 50)
    print("""
Basic Operations:
    +    Addition         (5 + 3)
    -    Subtraction      (10 - 4)
    *    Multiplication   (6 * 7)
    /    Division         (15 / 3)
    %    Modulus          (10 % 3)
    ^    Exponentiation   (2 ^ 8)

Functions:
    sqrt(x)   Square root   sqrt(16) = 4
    sin(x)    Sine          sin(0) = 0
    cos(x)    Cosine        cos(0) = 1
    tan(x)    Tangent       tan(0) = 0
    log(x)    Log base 10   log(100) = 2
    ln(x)     Natural log   ln(2.718) ≈ 1

Commands:
    help      Show this menu
    mem       Show stored memory
    clear     Clear memory
    exit      Quit calculator

Tips:
    - Results are automatically stored in memory
    - Use 'mem' in expressions: mem + 5
    - Parentheses work: (5 + 3) * 2
""")
    print("=" * 50)


def safe_eval(expression: str, memory: float = 0) -> float:
    """
    Safely evaluate a mathematical expression.
    
    Args:
        expression: Math expression as string
        memory: Current memory value for 'mem' variable
        
    Returns:
        Evaluated result
        
    Raises:
        ValueError: If expression is invalid or unsafe
    """
    # Normalize the expression
    expr = expression.lower().strip()
    
    # Replace common symbols and functions
    replacements = [
        ('^', '**'),
        ('sqrt(', 'math.sqrt('),
        ('sin(', 'math.sin('),
        ('cos(', 'math.cos('),
        ('tan(', 'math.tan('),
        ('log(', 'math.log10('),
        ('ln(', 'math.log('),
        ('pi', 'math.pi'),
        ('e', 'math.e'),
    ]
    
    for old, new in replacements:
        expr = expr.replace(old, new)
    
    # Define safe namespace
    safe_dict = {
        "__builtins__": {},
        "math": math,
        "mem": memory,
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
    }
    
    try:
        result = eval(expr, safe_dict)
        return float(result)
    except (SyntaxError, NameError, TypeError) as e:
        raise ValueError(f"Invalid expression: {e}")
    except ZeroDivisionError:
        raise ValueError("Division by zero")
    except Exception as e:
        raise ValueError(f"Calculation error: {e}")


def calculator():
    """Run the interactive advanced calculator."""
    memory = 0.0
    
    print("=" * 50)
    print("ADVANCED CALCULATOR")
    print("Type 'help' for commands, 'exit' to quit")
    print("=" * 50)
    
    while True:
        try:
            user_input = input("\ncalc> ").strip()
            
            if not user_input:
                continue
                
            cmd = user_input.lower()
            
            if cmd in ('exit', 'quit', 'q'):
                print("Goodbye!")
                break
            elif cmd in ('help', 'h', '?'):
                show_help()
                continue
            elif cmd == 'clear':
                memory = 0.0
                print("Memory cleared")
                continue
            elif cmd == 'mem':
                print(f"Memory: {memory}")
                continue
            
            # Evaluate the expression
            result = safe_eval(user_input, memory)
            memory = result
            
            # Format output
            if result == int(result):
                print(f"= {int(result)}")
            else:
                print(f"= {result:.6g}")
                
        except ValueError as e:
            print(f"Error: {e}")
            print("Type 'help' for available operations")
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")


def demo():
    """Demonstrate the calculator with examples."""
    print("ADVANCED CALCULATOR DEMO")
    print("=" * 50)
    
    examples = [
        "5 + 3",
        "2 ^ 10",
        "sqrt(144)",
        "sin(0)",
        "cos(0)",
        "log(1000)",
        "(5 + 3) * 2",
        "100 / 3",
    ]
    
    memory = 0.0
    for expr in examples:
        try:
            result = safe_eval(expr, memory)
            memory = result
            print(f"{expr:20} = {result:.6g}")
        except ValueError as e:
            print(f"{expr:20} Error: {e}")
    
    print("\n" + "=" * 50)
    print("Run 'python calculator.py' for interactive mode")


if __name__ == "__main__":
    import sys
    
    if "--demo" in sys.argv:
        demo()
    else:
        calculator()
