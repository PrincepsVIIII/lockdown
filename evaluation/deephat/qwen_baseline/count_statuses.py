def count_statuses(lines):
    status_counts = {}
    for line in lines:
        fields = line.split()
        if len(fields) == 5 and fields[3].isdigit() and 100 <= int(fields[3]) <= 599:
            status = int(fields[3])
            status_counts[status] = status_counts.get(status, 0) + 1
    return status_counts

