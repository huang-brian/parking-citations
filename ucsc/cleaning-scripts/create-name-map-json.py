#!/usr/bin/env python3
"""
Parse the canonical name matching file and create a JSON mapping
"""

import sys
from pathlib import Path
import json

def parse_canonical_file(input_file):
    """Parse the canonical name matching file and extract all mappings"""
    
    mappings = {}  # old_name -> canonical_name
    current_canonical = None
    skip_until_canonical = False
    
    with open(input_file, 'r') as f:
        for line in f:
            line = line.rstrip('\n')
            
            # Skip empty lines
            if not line.strip():
                continue
            
            # Check for canonical name line
            if line.startswith('CANONICAL NAME:'):
                current_canonical = line.replace('CANONICAL NAME:', '').strip()
                skip_until_canonical = False
            
            # Check for 'as is' marker
            elif line.strip() == 'as is':
                skip_until_canonical = True
            
            # Check for location entries (start with whitespace and numbers)
            elif line and line[0] == ' ':
                # Extract the location name (everything after the count)
                parts = line.strip().split(None, 1)  # Split on first whitespace
                if len(parts) == 2:
                    location_name = parts[1]
                    if skip_until_canonical:
                        # 'as is' entry - maps to itself
                        mappings[location_name] = location_name
                    elif current_canonical:
                        # Regular entry - maps to canonical
                        mappings[location_name] = current_canonical
    
    return mappings

def create_mapping_json(input_file, output_file):
    """Create a JSON mapping file"""
    
    print(f"Parsing: {input_file}")
    mappings = parse_canonical_file(input_file)
    
    # Group by canonical name
    canonical_groups = {}
    for original, canonical in mappings.items():
        if canonical not in canonical_groups:
            canonical_groups[canonical] = []
        if original != canonical:  # Don't include self-reference in variants
            canonical_groups[canonical].append(original)
    
    # Sort variants for each canonical
    for canonical in canonical_groups:
        canonical_groups[canonical].sort()
    
    # Sort by canonical name keys
    sorted_mapping = dict(sorted(canonical_groups.items()))
    
    # Write to JSON
    with open(output_file, 'w') as f:
        json.dump(sorted_mapping, f, indent=2)
    
    print(f"✓ Created mapping file: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 create_mapping.py <canonical_name_matching_file> [output.json]")
        print("\nExample:")
        print("  python3 create_mapping.py parking_lot_CANONICAL_NAME_matching.txt location_mapping.json")
        exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "location_mapping.json"
    
    if not Path(input_file).exists():
        print(f"Error: File not found at '{input_file}'")
        exit(1)
    
    create_mapping_json(input_file, output_file)