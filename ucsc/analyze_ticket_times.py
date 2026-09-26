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
    
    # Calculate summary statistics
    print(f"\n\n{'='*80}")
    print("SUMMARY STATISTICS")
    print(f"{'='*80}\n")
    
    # Global earliest and latest times
    global_earliest = results_df['Earliest Time'].min()
    global_latest = results_df['Latest Time'].max()
    
    print(f"Global Earliest Ticket Time (across all locations): {global_earliest}")
    print(f"Global Latest Ticket Time (across all locations): {global_latest}")
    
    # Calculate time span (hours between earliest and latest)
    earliest_dt = datetime.combine(datetime.today(), global_earliest)
    latest_dt = datetime.combine(datetime.today(), global_latest)
    time_span_hours = (latest_dt - earliest_dt).total_seconds() / 3600
    print(f"Time Span (earliest to latest): {time_span_hours:.1f} hours\n")
    
    # Average times across locations
    results_df['Time Span Hours'] = results_df.apply(
        lambda row: (datetime.combine(datetime.today(), row['Latest Time']) - 
                     datetime.combine(datetime.today(), row['Earliest Time'])).total_seconds() / 3600,
        axis=1
    )
    
    avg_time_span = results_df['Time Span Hours'].mean()
    print(f"Average time span per location: {avg_time_span:.1f} hours")
    print(f"Median time span per location: {results_df['Time Span Hours'].median():.1f} hours")
    print(f"Min time span: {results_df['Time Span Hours'].min():.1f} hours")
    print(f"Max time span: {results_df['Time Span Hours'].max():.1f} hours\n")
    
    # Ticket distribution
    print(f"Average tickets per location: {results_df['Ticket Count'].mean():.0f}")
    print(f"Median tickets per location: {results_df['Ticket Count'].median():.0f}")
    print(f"Max tickets at single location: {results_df['Ticket Count'].max()}")
    print(f"Min tickets at single location: {results_df['Ticket Count'].min()}")
    
    top_3 = results_df.nlargest(3, 'Ticket Count')
    print(f"\nTop 3 locations by ticket count:")
    for idx, (_, row) in enumerate(top_3.iterrows(), 1):
        print(f"  {idx}. {row['Location']}: {row['Ticket Count']} tickets")
    
    # Early morning and late evening analysis
    print(f"\n{'='*80}")
    print("ENFORCEMENT PATTERNS")
    print(f"{'='*80}\n")
    
    # Define time windows
    early_morning = pd.to_datetime('06:00', format='%H:%M').time()
    morning_peak = pd.to_datetime('09:00', format='%H:%M').time()
    evening = pd.to_datetime('17:00', format='%H:%M').time()
    late_evening = pd.to_datetime('20:00', format='%H:%M').time()
    
    locations_early = (results_df['Earliest Time'] <= early_morning).sum()
    locations_morning_peak = ((results_df['Earliest Time'] > early_morning) & 
                              (results_df['Earliest Time'] <= morning_peak)).sum()
    locations_evening = (results_df['Latest Time'] >= evening).sum()
    locations_late = (results_df['Latest Time'] >= late_evening).sum()
    
    print(f"Locations with earliest enforcement ≤ 6:00 AM: {locations_early}")
    print(f"Locations with earliest enforcement 6:00-9:00 AM: {locations_morning_peak}")
    print(f"Locations with enforcement continuing past 5:00 PM: {locations_evening}")
    print(f"Locations with enforcement past 8:00 PM: {locations_late}")
    
    # Calculate percentage of day with enforcement
    print(f"\nEnforcement Coverage:")
    coverage_results = []
    for _, row in results_df.iterrows():
        coverage = (row['Time Span Hours'] / 24) * 100
        coverage_results.append(coverage)
    
    print(f"Average % of day with enforcement activity: {sum(coverage_results)/len(coverage_results):.1f}%")
    print(f"Locations with 12+ hours of enforcement: {(results_df['Time Span Hours'] >= 12).sum()}")
    print(f"Locations with <4 hours of enforcement: {(results_df['Time Span Hours'] < 4).sum()}")
    
    # Hourly distribution
    print(f"\n{'='*80}")
    print("TICKETS ISSUED BY HOUR OF DAY")
    print(f"{'='*80}\n")
    
    # Extract hour from datetime
    df['Hour'] = df['Issue Date / Time'].dt.hour
    hourly_counts = df['Hour'].value_counts().sort_index()
    
    # Create a complete 24-hour range (0-23)
    all_hours = range(24)
    hourly_distribution = {hour: hourly_counts.get(hour, 0) for hour in all_hours}
    
    # Find max count for scaling bar chart
    max_count = max(hourly_distribution.values())
    
    # Print as table with ASCII bar chart
    print(f"{'Hour':<6} {'Time':<10} {'Count':<8} {'Bar Chart'}")
    print("-" * 80)
    
    for hour in all_hours:
        count = hourly_distribution[hour]
        time_str = f"{hour:02d}:00"
        # Create bar (scale to 40 chars max)
        bar_length = int((count / max_count) * 40) if max_count > 0 else 0
        bar = "█" * bar_length
        print(f"{hour:<6} {time_str:<10} {count:<8} {bar}")
    
    print(f"\nTotal tickets: {len(df)}")
    print(f"Peak hour: {hourly_counts.idxmax()}:00 ({hourly_counts.max()} tickets)")
    print(f"Slowest hour: {hourly_counts.idxmin()}:00 ({hourly_counts.min()} tickets)")

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