def is_present(input_string: str, filename: str) -> bool:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            contents = {line.strip() for line in f if line.strip()}
        return input_string.strip() in contents
    except FileNotFoundError:
        print(f"File not found: {filename}")
        return False
    except Exception as e:
        print(f"Error reading file: {e}")
        return False


if __name__ == "__main__":
    user_input = input("Enter string to check: ").strip()
    result = is_present(user_input, "SecurityQuestions.txt")
    print(result)