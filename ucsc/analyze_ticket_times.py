#!/usr/bin/env python3
"""
Parse parking tickets CSV and find earliest/latest ticket times for each location
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

def analyze_ticket_times(csv_file, output_file):
    """Analyze ticket times by location"""
    
    print(f"Reading CSV file: {csv_file}")
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} records\n")
    
    # Parse datetime column
    df['Issue Date / Time'] = pd.to_datetime(df['Issue Date / Time'], format='%m/%d/%Y %I:%M %p')
    
    # Extract time of day only
    df['Time of Day'] = df['Issue Date / Time'].dt.time
    
    # Group by location and find earliest/latest times
    results = []
    
    for location in sorted(df['Location'].unique()):
        location_data = df[df['Location'] == location]
        
        earliest_time = location_data['Time of Day'].min()
        latest_time = location_data['Time of Day'].max()
        ticket_count = len(location_data)
        
        results.append({
            'Location': location,
            'Earliest Time': earliest_time,
            'Latest Time': latest_time,
            'Ticket Count': ticket_count
        })
    
    # Create results dataframe
    results_df = pd.DataFrame(results)
    
    # Write to CSV
    results_df.to_csv(output_file, index=False)
    
    print(f"{'='*80}")
    print("TICKET TIME ANALYSIS BY LOCATION")
    print(f"{'='*80}\n")
    print(f"✓ Wrote results to: {output_file}\n")
    print(f"Total unique locations: {len(results_df)}")
    print(f"Total records analyzed: {len(df)}\n")
    
    # Display results
    print(f"{'Location':<50} {'Earliest':<10} {'Latest':<10} {'Count':<8}")
    print("-" * 80)
    
    for _, row in results_df.iterrows():
        location = row['Location'][:50] if len(row['Location']) > 50 else row['Location']
        earliest = str(row['Earliest Time'])
        latest = str(row['Latest Time'])
        count = str(row['Ticket Count'])
        print(f"{location:<50} {earliest:<10} {latest:<10} {count:<8}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_ticket_times.py <csv_file> [output_file]")
        print("\nExample:")
        print("  python3 analyze_ticket_times.py tickets_cleaned.csv ticket_times.csv")
        exit(1)
    
    csv_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "ticket_times.csv"
    
    if not Path(csv_file).exists():
        print(f"Error: CSV file not found at '{csv_file}'")
        exit(1)
    
    analyze_ticket_times(csv_file, output_file)