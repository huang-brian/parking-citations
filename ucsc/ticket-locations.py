#!/usr/bin/env python3
"""
Extract unique locations and their counts from parking tickets CSV file
"""

import pandas as pd
from pathlib import Path
import sys

def get_location_counts(filepath):
    """Get unique locations and their counts"""
    
    print(f"Reading CSV file: {filepath}\n")
    
    # Read CSV
    df = pd.read_csv(filepath)
    
    # Get location value counts
    location_counts = df['Location'].value_counts()
    
    # Sort by location name (alphabetically)
    location_counts = location_counts.sort_index()
    
    print(f"{'='*80}")
    print(f"UNIQUE LOCATIONS - {len(location_counts)} total")
    print(f"{'='*80}\n")
    
    for location, count in location_counts.items():
        print(f"{count:6d}  {location}")
    
    print(f"\n{'='*80}")
    print(f"Total records: {len(df)}")
    print(f"Unique locations: {len(location_counts)}")
    
    return location_counts

if __name__ == "__main__":
    # Check command line argument for file path
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = "parking_tickets.csv"  # Default filename
    
    # Check if file exists
    if not Path(csv_file).exists():
        print(f"Error: File not found at '{csv_file}'")
        print("\nUsage: python3 get_locations.py <path_to_csv_file>")
        print("\nExample: python3 get_locations.py ./my_tickets.csv")
        exit(1)
    
    # Get and display location counts
    get_location_counts(csv_file)