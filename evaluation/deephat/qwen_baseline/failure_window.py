def has_failure_burst(timestamps, n, window):
    if n <= 0 or window < 0:
        raise ValueError("n must be greater than 0 and window must be non-negative")
    if not timestamps:
        return False
    
    timestamps = sorted(timestamps)
    left = 0
    for right in range(len(timestamps)):
        while timestamps[right] - timestamps[left] > window:
            left += 1
        if right - left + 1 >= n:
            return True
    return False

