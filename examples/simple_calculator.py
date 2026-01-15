#!/usr/bin/env python3
"""
Simple Add-Only Calculator
Adds numbers up to 100,000
"""

def simple_add_calculator():
    """A very simple add-only calculator."""
    print("Simple Add-Only Calculator")
    print("Enter numbers to add them together.")
    print("Maximum allowed value: 100,000")
    print("Enter '=' to see total, 'c' to clear, 'q' to quit")
    print("-" * 40)
    
    total = 0
    
    while True:
        try:
            # Show current total
            print(f"\nCurrent total: {total}")
            
            # Get input
            user_input = input("Enter number: ").strip()
            
            # Check for commands
            if user_input.lower() == 'q':
                print(f"Final total: {total}")
                print("Goodbye!")
                break
                
            elif user_input.lower() == 'c':
                total = 0
                print("Calculator cleared.")
                continue
                
            elif user_input == '=':
                print(f"Total: {total}")
                continue
            
            # Try to add the number
            try:
                number = float(user_input)
                
                # Check range
                if abs(number) > 100000:
                    print(f"Error: {number} is too large! Must be between -100,000 and 100,000")
                    continue
                
                # Add to total
                total += number
                print(f"Added {number}")
                
            except ValueError:
                print(f"Error: '{user_input}' is not a valid number")
                print("Enter a number, '=', 'c', or 'q'")
                
        except KeyboardInterrupt:
            print(f"\n\nFinal total: {total}")
            break
        except Exception as e:
            print(f"Error: {e}")

# Run the calculator
if __name__ == "__main__":
    simple_add_calculator()