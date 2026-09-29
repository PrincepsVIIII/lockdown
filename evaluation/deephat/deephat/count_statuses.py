def count_statuses(lines):
    result = {}
    for line in lines:
        fields = line.split()
        if len(fields) == 5 and fields[3].isdigit() and 100 <= int(fields[3]) <= 599:
            status = int(fields[3])
            result[status] = result.get(status, 0) + 1
    return result

# Explanation:
1. The function takes an iterable of strings as input.
2. For each line, it splits into fields using whitespace.
3. It checks if there are exactly 5 fields and if the fourth field is a digit between 100 and 599.
4. If both conditions are met, it converts the status to an integer and updates the count in the result dictionary.
5. Finally, it returns the dictionary mapping status codes to their counts.
