"""
Fetch OSM boundary polygons for UCSC parking citation locations via Overpass API.

For each unique location in the citations CSV this script:
  1. Classifies it as a parking LOT, ROAD, or named AREA
  2. Builds a targeted Overpass query (different OSM tags per type)
  3. Fetches the geometry (polygon or linestring)
  4. Saves results as GeoJSON (one feature per location, with citation count)

Usage:
    pip install requests shapely pandas
    python fetch_ucsc_polygons.py

Outputs:
    ucsc_parking_polygons.geojson   — polygons/lines per location
    ucsc_polygon_misses.txt         — locations with no OSM geometry found
"""

import csv
import json
import time
import re
import requests
import pandas as pd
from collections import Counter
from shapely.geometry import shape, mapping, MultiPolygon, Polygon, LineString, MultiLineString
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
INPUT_FILE   = "2025_UCSC_parking_citations_clean.csv"
GEOJSON_OUT  = "ucsc_parking_polygons.geojson"
MISSES_OUT   = "ucsc_polygon_misses.txt"
CACHE_FILE   = "overpass_cache.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
RATE_LIMIT_S = 2.0   # Overpass: be conservative

# UCSC campus bounding box [south, west, north, east]
# Used in every query to avoid matching same-named places elsewhere
BBOX = (36.970, -122.080, 37.020, -122.020)
BBOX_STR = f"{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}"  # s,w,n,e for Overpass

# ── Location classification ───────────────────────────────────────────────────
ROAD_SUFFIXES = {
    "RD", "RD.", "DR", "DR.", "WAY", "AVE", "BLVD", "LN",
    "CT", "TRAIL", "ROAD", "DRIVE", "GRADE"
}

def classify(location: str) -> str:
    parts = location.split()
    if not parts:
        return "AREA"
    has_lot_num = re.match(r"^\d+[A-H]?$", parts[0]) is not None
    is_road     = parts[-1].upper() in ROAD_SUFFIXES
    if is_road:
        return "ROAD"
    if has_lot_num:
        return "LOT"
    return "AREA"

def strip_lot_number(location: str) -> str:
    """Remove leading lot number like '103A' or '112'."""
    parts = location.split(" ", 1)
    if re.match(r"^\d+[A-H]?$", parts[0]):
        return parts[1] if len(parts) > 1 else location
    return location

def clean_name(location: str) -> str:
    """Return the human-readable name without lot numbers."""
    return strip_lot_number(location).title()

# ── Overpass queries ──────────────────────────────────────────────────────────

def build_lot_query(name: str) -> str:
    """
    Search for parking amenities near UCSC by name.
    Tries both 'name' and 'ref' tags (UCSC uses lot numbers as refs).
    """
    return f"""
[out:json][timeout:30];
(
  way[amenity=parking](if: t["name"] =~ "{re.escape(name)}", i)({BBOX_STR});
  way[amenity=parking][ref="{name}"]({BBOX_STR});
  relation[amenity=parking](if: t["name"] =~ "{re.escape(name)}", i)({BBOX_STR});
  way[amenity=parking]({BBOX_STR});
);
out geom;
"""

def build_area_query(name: str) -> str:
    """
    Search for named areas: colleges, buildings, facilities.
    Cast a wide net across common OSM tags.
    """
    escaped = re.escape(name)
    return f"""
[out:json][timeout:30];
(
  way(if: t["name"] =~ "{escaped}", i)({BBOX_STR});
  relation(if: t["name"] =~ "{escaped}", i)({BBOX_STR});
);
out geom;
"""

def build_road_query(name: str) -> str:
    """Search for road/path geometries by name."""
    escaped = re.escape(name)
    return f"""
[out:json][timeout:30];
(
  way[highway](if: t["name"] =~ "{escaped}", i)({BBOX_STR});
  way[service](if: t["name"] =~ "{escaped}", i)({BBOX_STR});
);
out geom;
"""

# ── Geometry helpers ──────────────────────────────────────────────────────────

def overpass_element_to_geojson(el: dict) -> dict | None:
    """
    Convert an Overpass element with inline geometry to a GeoJSON geometry dict.
    Handles: way (polygon or linestring), relation (multipolygon).
    """
    etype = el.get("type")

    if etype == "way":
        coords = [(n["lon"], n["lat"]) for n in el.get("geometry", [])]
        if not coords:
            return None
        # Closed way → polygon, open way → linestring
        if coords[0] == coords[-1] and len(coords) >= 4:
            return {"type": "Polygon", "coordinates": [coords]}
        else:
            return {"type": "LineString", "coordinates": coords}

    if etype == "relation":
        # Build outer/inner rings
        outers, inners = [], []
        for member in el.get("members", []):
            if member.get("type") != "way":
                continue
            coords = [(n["lon"], n["lat"]) for n in member.get("geometry", [])]
            if not coords:
                continue
            role = member.get("role", "")
            if role == "inner":
                inners.append(coords)
            else:
                outers.append(coords)
        if not outers:
            return None
        rings = outers + inners
        if len(rings) == 1:
            return {"type": "Polygon", "coordinates": rings}
        return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}

    return None


def best_geometry(elements: list, loc_type: str) -> dict | None:
    """
    From a list of Overpass elements, pick the best geometry.
    For LOTs: prefer closed polygons. For ROADs: prefer linestrings.
    """
    geometries = []
    for el in elements:
        geo = overpass_element_to_geojson(el)
        if geo:
            geometries.append((el, geo))

    if not geometries:
        return None

    if loc_type == "ROAD":
        # Prefer linestrings
        lines = [(el, g) for el, g in geometries if g["type"] in ("LineString", "MultiLineString")]
        if lines:
            # Return a merged linestring of all matched road segments
            all_coords = []
            for _, g in lines:
                if g["type"] == "LineString":
                    all_coords.extend(g["coordinates"])
                else:
                    for part in g["coordinates"]:
                        all_coords.extend(part)
            return {"type": "LineString", "coordinates": all_coords}
        # Fall through to polygon if no lines found

    # For LOTs and AREAs: prefer polygons, pick largest by area
    polys = [(el, g) for el, g in geometries if g["type"] in ("Polygon", "MultiPolygon")]
    if polys:
        def area_key(item):
            try:
                return shape(item[1]).area
            except Exception:
                return 0
        _, best = max(polys, key=area_key)
        return best

    # Fallback: return first geometry found
    return geometries[0][1]


# ── Overpass fetch with caching ───────────────────────────────────────────────

def fetch_overpass(query: str, cache: dict, cache_key: str) -> list:
    if cache_key in cache:
        return cache[cache_key]

    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=60)
    resp.raise_for_status()
    elements = resp.json().get("elements", [])
    cache[cache_key] = elements
    return elements


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load citations
    print(f"Loading {INPUT_FILE} …")
    df = pd.read_csv(INPUT_FILE)
    loc_counts = Counter(df["Location"].dropna())
    unique_locs = sorted(loc_counts.keys())
    print(f"  {len(df):,} citations | {len(unique_locs)} unique locations\n")

    # Load cache
    cache_path = Path(CACHE_FILE)
    cache: dict = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    features = []
    misses   = []

    for i, loc in enumerate(unique_locs, 1):
        loc_type   = classify(loc)
        name_clean = clean_name(loc)           # e.g. "East Field House"
        name_bare  = strip_lot_number(loc)     # e.g. "EAST FIELD HOUSE"

        # Build query based on type
        if loc_type == "LOT":
            # Try with the bare name (no lot number)
            query     = build_lot_query(name_clean)
            cache_key = f"lot:{name_bare}"
        elif loc_type == "ROAD":
            road_name = re.sub(r"^\d+[A-H]?\s+", "", loc)  # strip number if present
            road_name = road_name.replace(" RD.", " Road").replace(" RD", " Road") \
                                 .replace(" DR.", " Drive").replace(" DR", " Drive") \
                                 .title()
            query     = build_road_query(road_name)
            cache_key = f"road:{road_name}"
        else:
            query     = build_area_query(name_clean)
            cache_key = f"area:{name_clean}"

        # Fetch
        if cache_key not in cache:
            time.sleep(RATE_LIMIT_S)

        try:
            elements = fetch_overpass(query, cache, cache_key)
            cache_path.write_text(json.dumps(cache))
        except Exception as e:
            print(f"[{i:3d}/{len(unique_locs)}] ERROR  {loc}: {e}")
            misses.append(loc)
            continue

        geo = best_geometry(elements, loc_type)

        if geo is None:
            print(f"[{i:3d}/{len(unique_locs)}] MISS   {loc}")
            misses.append(loc)
            continue

        print(f"[{i:3d}/{len(unique_locs)}] OK {loc_type:4s}  {loc}  ({geo['type']})")
        features.append({
            "type": "Feature",
            "geometry": geo,
            "properties": {
                "location":      loc,
                "location_type": loc_type,
                "name_clean":    name_clean,
                "citation_count": loc_counts[loc],
            }
        })

    # Save GeoJSON
    geojson = {"type": "FeatureCollection", "features": features}
    Path(GEOJSON_OUT).write_text(json.dumps(geojson, indent=2))
    print(f"\nSaved {len(features)} features → {GEOJSON_OUT}")

    # Save misses
    Path(MISSES_OUT).write_text("\n".join(misses))
    print(f"Saved {len(misses)} misses → {MISSES_OUT}")

    # Summary
    n_total = len(unique_locs)
    n_hit   = len(features)
    print(f"\nMatch rate: {n_hit}/{n_total} ({100*n_hit/n_total:.1f}%)")
    if misses:
        print("\nMissed locations (will need manual polygons or Nominatim centroid fallback):")
        for m in misses:
            print(f"  {m}")


if __name__ == "__main__":
    main()
