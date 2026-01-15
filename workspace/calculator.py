def add_only_calculator():
    print("--- Add-Only Calculator (Max 100,000) ---")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        try:
            user_input1 = input("\nEnter first number: ")
            if user_input1.lower() in ['exit', 'quit']:
                break
            
            user_input2 = input("Enter second number: ")
            if user_input2.lower() in ['exit', 'quit']:
                break

            num1 = float(user_input1)
            num2 = float(user_input2)
            
            result = num1 + num2
            
            if result > 100000:
                print(f"Error: Result {result} exceeds the limit of 100,000.")
            else:
                print(f"Result: {result}")
                
        except ValueError:
            print("Invalid input. Please enter numeric values.")

if __name__ == "__main__":
    add_only_calculator()
