import pstats

# Create a pstats.Stats object
stats = pstats.Stats('your-file')

# Sort the statistics by the cumulative time spent in the function
stats.sort_stats('cumulative')

# Print the statistics
stats.print_stats(10)
