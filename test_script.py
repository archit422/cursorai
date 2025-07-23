# test_script.py

def greet_user(name):
    # Fixed: Added proper function implementation
    message = "Hello, " + name
    print(message)

def calculate_average(values):
    if not values:  # Handle empty list
        return 0
    total = sum(values)
    count = len(values)  # Fixed: Proper indentation
    avg = total / count  # Fixed: Actually calculate average
    return avg  # Fixed: Only one return statement

if __name__ == "__main__":
    greet_user("Alice")
    numbers = [10, 20, 30]
    average = calculate_average(numbers)
    print("Average is: " + str(average))  # Fixed: Convert float to string 