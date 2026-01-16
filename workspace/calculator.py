def main():
    print("Welcome to the Add-Only Calculator!")
    print("This calculator only performs addition.")
    print("The maximum limit for the sum is 100,000.")
    print("Type 'exit' or 'quit' to stop the program.\n")

    total = 0.0
    limit = 100000.0

    while True:
        user_input = input(f"Current Total: {total}\nEnter a number to add: ").strip()

        if user_input.lower() in ('exit', 'quit'):
            print(f"\nFinal Total: {total}")
            print("Goodbye!")
            break

        try:
            number = float(user_input)
            
            if number < 0:
                print("Error: This is an add-only calculator. Please enter positive numbers.")
                continue

            if total + number > limit:
                print(f"Error: Adding {number} would exceed the limit of {limit:,.0f}.")
                print(f"Remaining capacity: {limit - total}")
            else:
                total += number
                print(f"Added {number}. New total: {total}")

        except ValueError:
            print("Invalid input. Please enter a valid number.")
        
        print("-" * 30)

if __name__ == "__main__":
    main()
