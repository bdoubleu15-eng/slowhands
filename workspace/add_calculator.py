def add_only_calculator():
    print("Welcome to the Add-Only Calculator!")
    print("This calculator only performs addition.")
    print("The maximum limit for the total sum is 100,000.")
    print("Type 'exit' or 'quit' to stop and see the final result.")

    total = 0
    LIMIT = 100000

    while True:
        user_input = input(f"Current Total: {total}. Enter a number to add: ")

        if user_input.lower() in ['exit', 'quit']:
            break

        try:
            number = float(user_input)
            
            if number < 0:
                print("Please enter positive numbers only (it's an add-only calculator!).")
                continue

            if total + number > LIMIT:
                print(f"Error: Adding {number} would exceed the limit of {LIMIT}.")
                print(f"Remaining capacity: {LIMIT - total}")
            else:
                total += number
                print(f"Added {number}. New Total: {total}")

        except ValueError:
            print("Invalid input. Please enter a valid number.")

    print(f"Final Total: {total}")
    print("Goodbye!")

if __name__ == "__main__":
    add_only_calculator()
