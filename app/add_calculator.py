def add_calculator():
    print("Welcome to the Add-Only Calculator!")
    print("The maximum limit is 100,000.")
    print("Type 'q' or 'exit' to quit.")
    
    total = 0
    limit = 100000

    while True:
        print(f"\nCurrent Total: {total}")
        user_input = input("Enter a number to add: ").strip().lower()

        if user_input in ('q', 'exit'):
            print("Goodbye!")
            break

        try:
            number = float(user_input)
            
            if total + number > limit:
                print(f"Error: Adding {number} would exceed the limit of {limit}.")
            else:
                total += number
                
        except ValueError:
            print("Invalid input. Please enter a number or 'q' to quit.")

if __name__ == "__main__":
    add_calculator()
