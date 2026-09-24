#!/usr/bin/env python3
"""
Analyze parking tickets CSV file for:
1. Unique values in key fields (Location, Viol Code, Violation, Make, Color, Status)
2. Format anomalies in datetime and amount fields
"""

import pandas as pd
import re
from datetime import datetime
from pathlib import Path

def validate_datetime(date_str):
    """Check if string matches format M/D/YYYY H:MM AM/PM"""
    pattern = r'^\d{1,2}/\d{1,2}/\d{4}\s\d{1,2}:\d{2}\s(?:AM|PM)$'
    return bool(re.match(pattern, str(date_str)))

def validate_amount(amount_str):
    """Check if string matches format $XX.XX"""
    pattern = r'^\$\d+\.\d{2}$'
    return bool(re.match(pattern, str(amount_str)))

def analyze_csv(filepath, nrows=None):
    """Analyze the parking tickets CSV file"""
    
    print(f"Reading CSV file: {filepath}")
    
    # Read CSV, skipping the first 2 header rows
    df = pd.read_csv(filepath, skiprows=2, nrows=nrows)
    
    print(f"\n{'='*80}")
    print(f"ANALYSIS RESULTS - {len(df)} records processed")
    print(f"{'='*80}\n")
    
    # Fields to analyze for unique values
    unique_fields = ['Location', 'Viol Code', 'Violation', 'Make', 'Color', 'Status']
    
    print("UNIQUE VALUES IN KEY FIELDS")
    print("-" * 80)
    for field in unique_fields:
        if field in df.columns:
            unique_values = df[field].dropna().unique()
            print(f"\n{field}: ({len(unique_values)} unique values)")
            print(f"  {sorted(unique_values)}")
    
    # Analyze datetime format issues
    print(f"\n\n{'='*80}")
    print("DATETIME FORMAT VALIDATION (Issue Date / Time)")
    print("-" * 80)
    
    if 'Issue Date / Time' in df.columns:
        datetime_col = 'Issue Date / Time'
        invalid_datetimes = []
        
        for idx, val in df[datetime_col].items():
            if pd.notna(val) and not validate_datetime(val):
                invalid_datetimes.append({
                    'Row': idx + 2,  # +2 for 0-indexing and header
                    'Ticket #': df.loc[idx, 'Ticket #'] if 'Ticket #' in df.columns else 'N/A',
                    'Value': str(val)
                })
        
        if invalid_datetimes:
            print(f"\n❌ Found {len(invalid_datetimes)} records with INVALID datetime format:")
            print(f"   Expected format: M/D/YYYY H:MM AM/PM (e.g., '6/3/2024 8:06 AM')\n")
            for record in invalid_datetimes[:20]:  # Show first 20
                print(f"   Row {record['Row']} | Ticket {record['Ticket #']}: {record['Value']}")
            if len(invalid_datetimes) > 20:
                print(f"   ... and {len(invalid_datetimes) - 20} more")
        else:
            print(f"\n✓ All {len(df)} datetime values are valid")
    
    # Analyze amount format issues
    print(f"\n\n{'='*80}")
    print("AMOUNT FORMAT VALIDATION (Amount)")
    print("-" * 80)
    
    if 'Amount' in df.columns:
        amount_col = 'Amount'
        invalid_amounts = []
        
        for idx, val in df[amount_col].items():
            if pd.notna(val) and not validate_amount(val):
                invalid_amounts.append({
                    'Row': idx + 2,
                    'Ticket #': df.loc[idx, 'Ticket #'] if 'Ticket #' in df.columns else 'N/A',
                    'Value': str(val)
                })
        
        if invalid_amounts:
            print(f"\n❌ Found {len(invalid_amounts)} records with INVALID amount format:")
            print(f"   Expected format: $XX.XX (e.g., '$110.00')\n")
            for record in invalid_amounts[:20]:
                print(f"   Row {record['Row']} | Ticket {record['Ticket #']}: {record['Value']}")
            if len(invalid_amounts) > 20:
                print(f"   ... and {len(invalid_amounts) - 20} more")
        else:
            print(f"\n✓ All {len(df)} amount values are valid")
    
    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print("-" * 80)
    print(f"Total records: {len(df)}")
    print(f"Unique Locations: {df['Location'].nunique() if 'Location' in df.columns else 'N/A'}")
    print(f"Unique Viol Codes: {df['Viol Code'].nunique() if 'Viol Code' in df.columns else 'N/A'}")
    print(f"Unique Violations: {df['Violation'].nunique() if 'Violation' in df.columns else 'N/A'}")
    print(f"Unique Makes: {df['Make'].nunique() if 'Make' in df.columns else 'N/A'}")
    print(f"Unique Colors: {df['Color'].nunique() if 'Color' in df.columns else 'N/A'}")
    print(f"Unique Statuses: {df['Status'].nunique() if 'Status' in df.columns else 'N/A'}")
    print(f"\nDatetime format issues: {len(invalid_datetimes) if 'Issue Date / Time' in df.columns else 'N/A'}")
    print(f"Amount format issues: {len(invalid_amounts) if 'Amount' in df.columns else 'N/A'}")
    
    return df, invalid_datetimes, invalid_amounts

def export_results(df, invalid_datetimes, invalid_amounts, output_dir="."):
    """Export detailed results to files"""
    
    print(f"\n\n{'='*80}")
    print("EXPORTING RESULTS")
    print("-" * 80)
    
    # Export unique values to CSV
    unique_fields = ['Location', 'Viol Code', 'Violation', 'Make', 'Color', 'Status']
    
    for field in unique_fields:
        if field in df.columns:
            unique_vals = sorted(df[field].dropna().unique())
            with open(f"{output_dir}/unique_{field.lower().replace(' ', '_')}.txt", 'w') as f:
                f.write(f"Unique values in '{field}' ({len(unique_vals)} total):\n")
                f.write("=" * 60 + "\n\n")
                for val in unique_vals:
                    f.write(f"{val}\n")
            print(f"✓ Exported: unique_{field.lower().replace(' ', '_')}.txt ({len(unique_vals)} values)")
    
    # Export invalid records
    if invalid_datetimes:
        invalid_dt_df = pd.DataFrame(invalid_datetimes)
        invalid_dt_df.to_csv(f"{output_dir}/invalid_datetimes.csv", index=False)
        print(f"✓ Exported: invalid_datetimes.csv ({len(invalid_datetimes)} records)")
    
    if invalid_amounts:
        invalid_amt_df = pd.DataFrame(invalid_amounts)
        invalid_amt_df.to_csv(f"{output_dir}/invalid_amounts.csv", index=False)
        print(f"✓ Exported: invalid_amounts.csv ({len(invalid_amounts)} records)")

if __name__ == "__main__":
    import sys
    
    # Check command line argument for file path
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = "parking_tickets.csv"  # Default filename
    
    # Check if file exists
    if not Path(csv_file).exists():
        print(f"Error: File not found at '{csv_file}'")
        print("\nUsage: python3 analyze_tickets.py <path_to_csv_file>")
        print("\nExample: python3 analyze_tickets.py ./my_tickets.csv")
        exit(1)
    
    # Run analysis (remove nrows parameter to process all rows)
    df, invalid_datetimes, invalid_amounts = analyze_csv(csv_file)
    
    # Export results to separate files for easy review
    output_dir = Path(csv_file).parent
    export_results(df, invalid_datetimes, invalid_amounts, output_dir)