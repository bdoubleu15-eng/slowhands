#!/usr/bin/env python3
"""
Add-Only Calculator with 100,000 Limit
A simple calculator that only performs addition with a maximum value of 100,000
"""

def add_numbers(a, b, limit=100000):
    """
    Add two numbers with limit checking.
    
    Args:
        a: First number
        b: Second number
        limit: Maximum allowed value (default: 100,000)
        
    Returns:
        Sum of a and b if within limit
        
    Raises:
        ValueError: If any number or the result exceeds the limit
    """
    # Check individual numbers
    if abs(a) > limit:
        raise ValueError(f"Number {a:,} exceeds the limit of {limit:,}")
    if abs(b) > limit:
        raise ValueError(f"Number {b:,} exceeds the limit of {limit:,}")
    
    # Calculate result
    result = a + b
    
    # Check result
    if abs(result) > limit:
        raise ValueError(f"Result {result:,} exceeds the limit of {limit:,}")
    
    return result

def add_multiple_numbers(numbers, limit=100000):
    """
    Add multiple numbers with limit checking.
    
    Args:
        numbers: List of numbers to add
        limit: Maximum allowed value (default: 100,000)
        
    Returns:
        Sum of all numbers if within limit
        
    Raises:
        ValueError: If any number or the running total exceeds the limit
    """
    total = 0
    
    for i, num in enumerate(numbers, 1):
        # Check individual number
        if abs(num) > limit:
            raise ValueError(f"Number {num:,} at position {i} exceeds the limit of {limit:,}")
        
        # Add to running total
        total += num
        
        # Check running total
        if abs(total) > limit:
            raise ValueError(f"Running total {total:,} exceeds the limit of {limit:,}")
    
    return total

def interactive_calculator():
    """
    Interactive version of the add-only calculator.
    Allows user to enter numbers one by one.
    """
    print("=" * 50)
    print("ADD-ONLY CALCULATOR")
    print("Only performs addition")
    print("Maximum value: 100,000")
    print("=" * 50)
    
    numbers = []
    running_total = 0
    
    while True:
        try:
            # Get user input
            prompt = f"\nEnter number {len(numbers)+1}"
            if numbers:
                prompt += f" (current total: {running_total:,})"
            prompt += " or '=' to finish, 'q' to quit: "
            
            user_input = input(prompt).strip()
            
            # Check for commands
            if user_input.lower() == 'q':
                print("\nGoodbye!")
                break
                
            if user_input == '=':
                if len(numbers) < 2:
                    print("Please enter at least 2 numbers before calculating.")
                    continue
                
                print(f"\n{' + '.join(str(n) for n in numbers)} = {running_total:,}")
                print("=" * 50)
                
                # Reset for new calculation
                numbers = []
                running_total = 0
                continue
            
            # Convert to number
            try:
                num = int(user_input)
            except ValueError:
                num = float(user_input)
            
            # Check limit for individual number
            if abs(num) > 100000:
                print(f"Error: {num:,} exceeds the limit of 100,000")
                continue
            
            # Check if adding would exceed limit
            new_total = running_total + num
            if abs(new_total) > 100000:
                print(f"Error: Adding {num:,} would make total {new_total:,}, exceeding 100,000")
                continue
            
            # Add the number
            numbers.append(num)
            running_total = new_total
            
            print(f"Added {num:,}. New total: {running_total:,}")
            
        except ValueError as e:
            print(f"Invalid input: {e}")
        except KeyboardInterrupt:
            print("\n\nCalculator terminated.")
            break

def main():
    """Main function to demonstrate the calculator."""
    print("ADD-ONLY CALCULATOR DEMONSTRATION")
    print("=" * 50)
    
    # Example 1: Simple addition
    print("\nExample 1: Simple addition within limit")
    try:
        result = add_numbers(25000, 35000)
        print(f"25,000 + 35,000 = {result:,}")
    except ValueError as e:
        print(f"Error: {e}")
    
    # Example 2: Multiple numbers
    print("\nExample 2: Adding multiple numbers")
    try:
        numbers = [10000, 20000, 30000, 15000]
        result = add_multiple_numbers(numbers)
        print(f"{' + '.join(str(n) for n in numbers)} = {result:,}")
    except ValueError as e:
        print(f"Error: {e}")
    
    # Example 3: Exceeding limit
    print("\nExample 3: Attempting to exceed limit")
    try:
        result = add_numbers(80000, 30000)
        print(f"80,000 + 30,000 = {result:,}")
    except ValueError as e:
        print(f"Error: {e}")
    
    # Example 4: Negative numbers
    print("\nExample 4: Working with negative numbers")
    try:
        result = add_numbers(-40000, 90000)
        print(f"-40,000 + 90,000 = {result:,}")
    except ValueError as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 50)
    print("To use the interactive calculator, run:")
    print("python add_only_calculator_100k.py --interactive")
    print("=" * 50)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_calculator()
    else:
        main()