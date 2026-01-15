def main():
    limit = 100000
    total = 0
    
    print(f"--- Add-Only Calculator (Limit: {limit}) ---")
    print("Type a number to add it to the total.")
    print("Type 'q' to quit.")
    
    while True:
        user_input = input(f"\nCurrent Total: {total}\nEnter number to add: ").strip()
        
        if user_input.lower() == 'q':
            print(f"Final Total: {total}")
            break
            
        try:
            number = float(user_input)
            
            if number < 0:
                print("Error: This is an add-only calculator. Please enter positive numbers.")
                continue
                
            if total + number > limit:
                print(f"Error: Adding {number} would exceed the limit of {limit}.")
            else:
                total += number
                # If it's a whole number, display it as an integer for cleanliness
                if total.is_integer():
                    total = int(total)
                    
        except ValueError:
            print("Invalid input. Please enter a number or 'q' to quit.")

if __name__ == "__main__":
    main()
