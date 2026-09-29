def merge_intervals(intervals):
    if not intervals:
        return []
    
    # Sort intervals by start time
    intervals.sort(key=lambda x: x[0])
    
    # Initialize result with first interval
    merged = [intervals[0]]
    
    # Iterate through remaining intervals
    for current in intervals[1:]:
        last = merged[-1]
        
        # If current interval overlaps or touches last interval
        if current[0] <= last[1] + 1:
            # Merge them by taking max end
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            # No overlap, add current interval
            merged.append(current)
    
    return merged

