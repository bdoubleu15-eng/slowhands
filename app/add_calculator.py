def main():
    print("Welcome to the Add-Only Calculator!")
    print("The limit is 100,000.")
    print("Type 'exit' or 'quit' to stop.")
    
    total = 0
    limit = 100000

    while True:
        user_input = input(f"Current Total: {total}. Enter a number to add: ")

        if user_input.lower() in ['exit', 'quit']:
            print(f"Final Total: {total}")
            print("Goodbye!")
            break

        try:
            number = float(user_input)
            
            if number < 0:
                print("This is an add-only calculator. Please enter positive numbers.")
                continue

            if total + number > limit:
                print(f"Error: Adding {number} would exceed the limit of {limit}.")
            else:
                total += number
                # Check if it's an integer to print cleanly
                if total.is_integer():
                    total = int(total)
                
        except ValueError:
            print("Invalid input. Please enter a valid number.")

if __name__ == "__main__":
    main()
