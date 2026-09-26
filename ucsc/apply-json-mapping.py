#!/usr/bin/env python3
"""
Apply canonical location names from JSON mapping to parking tickets CSV file
"""

import sys
from pathlib import Path
import json
import pandas as pd

def load_mapping_json(json_file):
    """Load the JSON mapping file and create old_name -> canonical_name dictionary"""
    
    with open(json_file, 'r') as f:
        canonical_groups = json.load(f)
    
    # Create reverse mapping: old_name -> canonical_name
    mapping = {}
    for canonical, variants in canonical_groups.items():
        # Map canonical to itself
        mapping[canonical] = canonical
        # Map each variant to canonical
        for variant in variants:
            mapping[variant] = canonical
    
    return mapping

def apply_mapping_to_csv(csv_file, json_file, output_file):
    """Apply canonical location mapping to CSV file"""
    
    print(f"Loading mapping from: {json_file}")
    mapping = load_mapping_json(json_file)
    print(f"Loaded {len(mapping)} location mappings\n")
    
    print(f"Reading CSV file: {csv_file}")
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} records\n")
    
    # Track statistics
    original_locations = set(df['Location'].dropna().unique())
    unmapped = set()
    mapped_count = 0
    
    # Apply mapping function
    def map_location(loc):
        nonlocal mapped_count, unmapped
        if pd.isna(loc):
            return loc
        loc_str = str(loc).strip()
        if loc_str in mapping:
            mapped_count += 1
            return mapping[loc_str]
        else:
            unmapped.add(loc_str)
            return loc_str
    
    # Apply the mapping
    df['Location'] = df['Location'].apply(map_location)
    
    # Write output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    print(f"{'='*80}")
    print("MAPPING RESULTS")
    print(f"{'='*80}\n")
    print(f"✓ Wrote cleaned data to: {output_file}\n")
    print(f"Total records processed: {len(df)}")
    print(f"Original unique locations: {len(original_locations)}")
    print(f"Unique locations after mapping: {df['Location'].nunique()}")
    print(f"Records with mapped locations: {mapped_count}")
    
    if unmapped:
        print(f"\n⚠ WARNING: {len(unmapped)} locations NOT found in mapping file:")
        for loc in sorted(unmapped):
            print(f"  - {loc}")
        print(f"\nThese locations were NOT changed. Check your mapping file.")
    else:
        print(f"\n✓ All locations successfully mapped!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 apply_json_mapping.py <csv_file> <json_mapping_file> [output_file]")
        print("\nExample:")
        print("  python3 apply_json_mapping.py tickets.csv location_mapping.json tickets_cleaned.csv")
        exit(1)
    
    csv_file = sys.argv[1]
    json_file = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else "tickets_cleaned.csv"
    
    # Check if files exist
    if not Path(csv_file).exists():
        print(f"Error: CSV file not found at '{csv_file}'")
        exit(1)
    
    if not Path(json_file).exists():
        print(f"Error: JSON mapping file not found at '{json_file}'")
        exit(1)
    
    # Apply mapping
    apply_mapping_to_csv(csv_file, json_file, output_file)