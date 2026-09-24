import json
import re
import time
import pandas as pd
import requests

# ---------------------------------------------------------
# 1. Configuration & Data Loading
# ---------------------------------------------------------
CSV_FILE = "2025_UCSC_parking_citations_clean.csv"
OUTPUT_GEOJSON = "ucsc_location_reference.geojson"
OUTPUT_CSV = "ucsc_location_reference.csv"

# UCSC Bounding Box (South, West, North, East)
BBOX = "36.96,-122.09,37.02,-122.03"

df = pd.read_csv(CSV_FILE)
unique_locations = df["Location"].dropna().unique()

# Known aliases for fallback parent lookup
PARENT_FALLBACKS = {
    "FSH": "FAMILY STUDENT HOUSING",
    "ARC": "ACADEMIC RESOURCE CENTER"
}

# ---------------------------------------------------------
# 2. Overpass API Fetching (with requests & SSL support)
# ---------------------------------------------------------
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

overpass_query = f"""
[out:json][timeout:90];
(
  way["amenity"="parking"]({BBOX});
  relation["amenity"="parking"]({BBOX});
  way["building"]({BBOX});
  relation["building"]({BBOX});
  way["highway"]({BBOX});
  relation["place"="hamlet"]({BBOX});
  way["landuse"="education"]({BBOX});
);
out body geom;
"""

headers = {
    "User-Agent": "UCSC_Parking_Geocoder/1.0 (ucsc-parking-citations-project)",
    "Accept": "*/*",
}

osm_raw = None
print(f"Fetching OSM data for UCSC bounding box ({BBOX})...")

for url in OVERPASS_URLS:
    try:
        resp = requests.post(
            url, data={"data": overpass_query}, headers=headers, timeout=60
        )
        resp.raise_for_status()
        osm_raw = resp.json()
        print(f"Successfully fetched data from {url}")
        break
    except requests.exceptions.RequestException as e:
        print(
            f"Warning: Failed to fetch from {url} ({e}). Retrying with fallback server..."
        )
        time.sleep(2)

if not osm_raw:
    raise RuntimeError("Could not fetch Overpass data from any endpoint.")

elements = osm_raw.get("elements", [])
print(f"Retrieved {len(elements)} OSM elements.")


# ---------------------------------------------------------
# 3. Geometry & Feature Extraction
# ---------------------------------------------------------
def extract_coordinates(element):
    """Converts OSM way/relation geometry into GeoJSON geometry format."""
    el_type = element.get("type")
    tags = element.get("tags", {})
    is_highway = "highway" in tags

    if "geometry" in element:
        coords = [[pt["lon"], pt["lat"]] for pt in element["geometry"]]
        if len(coords) < 2:
            return None, None

        # Roads stay as LineString
        if is_highway:
            return "LineString", coords

        # Polygons must close
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        if len(coords) >= 4:
            return "Polygon", [coords]

    return None, None


# Index OSM features
osm_features = []
for el in elements:
    tags = el.get("tags", {})
    geom_type, coords = extract_coordinates(el)
    if not geom_type:
        continue

    ref = str(tags.get("ref", "")).strip().upper()
    name = str(tags.get("name", "")).strip().upper()
    alt_name = str(tags.get("alt_name", "")).strip().upper()
    building = str(tags.get("building", "")).strip().upper()

    osm_features.append(
        {
            "osm_id": el.get("id"),
            "osm_type": el.get("type"),
            "ref": ref,
            "name": name,
            "alt_name": alt_name,
            "building": building,
            "tags": tags,
            "geom_type": geom_type,
            "coords": coords,
        }
    )


# ---------------------------------------------------------
# 4. Matching & Fallback Logic
# ---------------------------------------------------------
def calculate_centroid(geom_type, coords):
    """Computes basic centroid [lon, lat] for CSV tabular export."""
    if geom_type == "LineString":
        lons = [p[0] for p in coords]
        lats = [p[1] for p in coords]
    elif geom_type == "Polygon":
        lons = [p[0] for p in coords[0]]
        lats = [p[1] for p in coords[0]]
    else:
        return None, None
    return sum(lons) / len(lons), sum(lats) / len(lats)


matched_records = []

for loc in sorted(unique_locations):
    loc_clean = loc.strip().upper()

    # Clean off sub-location noise tags for primary matching
    loc_base = re.sub(
        r"\b(PARKMOBILE|LOADING DOCK|APTS|APARTMENTS|DORMS)\b", "", loc_clean
    ).strip()

    # Extract leading lot number (e.g. '138', '103A', '150B')
    match = re.match(r"^(\d+[A-Z]?)\b", loc_clean)
    lot_num = match.group(1) if match else None

    matched_feature = None
    match_type = None

    # Step 1: Match by Parking Lot Number (ref tag in OSM)
    if lot_num:
        for feat in osm_features:
            if feat["geom_type"] == "Polygon" and (
                feat["ref"] == lot_num or feat["name"] == lot_num
            ):
                matched_feature = feat
                match_type = "exact_lot_ref"
                break

    # Step 2: Match by Building/Place Name
    if not matched_feature:
        for feat in osm_features:
            if feat["name"] and (
                feat["name"] in loc_base or loc_base in feat["name"]
            ):
                matched_feature = feat
                match_type = "exact_name"
                break

    # Step 3: Road LineString Match
    if not matched_feature:
        for feat in osm_features:
            if feat["geom_type"] == "LineString" and feat["name"]:
                if feat["name"] in loc_clean or loc_clean in feat["name"]:
                    matched_feature = feat
                    match_type = "road_linestring"
                    break

    # Step 4: Fallback to Parent Building / College Polygon
    if not matched_feature:
        fallback_name = None
        for key, target in PARENT_FALLBACKS.items():
            if key in loc_clean:
                fallback_name = target
                break

        if not fallback_name and lot_num:
            # Strip lot number and use description
            fallback_name = re.sub(r"^\d+[A-Z]?\s*", "", loc_base)

        if fallback_name:
            for feat in osm_features:
                if feat["name"] and (
                    fallback_name in feat["name"] or feat["name"] in fallback_name
                ):
                    matched_feature = feat
                    match_type = "fallback_parent_polygon"
                    break

    # Record matched result
    if matched_feature:
        c_lon, c_lat = calculate_centroid(
            matched_feature["geom_type"], matched_feature["coords"]
        )
        matched_records.append(
            {
                "location_raw": loc,
                "match_type": match_type,
                "osm_id": matched_feature["osm_id"],
                "osm_type": matched_feature["osm_type"],
                "matched_name": matched_feature["name"] or matched_feature["ref"],
                "geometry_type": matched_feature["geom_type"],
                "longitude": c_lon,
                "latitude": c_lat,
                "coordinates": matched_feature["coords"],
            }
        )
    else:
        matched_records.append(
            {
                "location_raw": loc,
                "match_type": "unmatched",
                "osm_id": None,
                "osm_type": None,
                "matched_name": None,
                "geometry_type": None,
                "longitude": None,
                "latitude": None,
                "coordinates": None,
            }
        )

# ---------------------------------------------------------
# 5. Export GeoJSON, CSV Reference Tables & Unmatched List
# ---------------------------------------------------------
geojson_features = []
csv_rows = []

for r in matched_records:
    csv_rows.append({
        "Location": r["location_raw"],
        "match_type": r["match_type"],
        "osm_id": r["osm_id"],
        "osm_type": r["osm_type"],
        "matched_name": r["matched_name"],
        "geometry_type": r["geometry_type"],
        "longitude": r["longitude"],
        "latitude": r["latitude"]
    })

    if r["coordinates"]:
        geojson_features.append({
            "type": "Feature",
            "geometry": {
                "type": r["geometry_type"],
                "coordinates": r["coordinates"]
            },
            "properties": {
                "location": r["location_raw"],
                "match_type": r["match_type"],
                "osm_id": r["osm_id"],
                "osm_type": r["osm_type"],
                "matched_name": r["matched_name"]
            }
        })

# Save main outputs
with open(OUTPUT_GEOJSON, "w") as f:
    json.dump({"type": "FeatureCollection", "features": geojson_features}, f, indent=2)

df_ref = pd.DataFrame(csv_rows)
df_ref.to_csv(OUTPUT_CSV, index=False)

# Extract and export unmatched locations
unmatched_df = df_ref[df_ref["match_type"] == "unmatched"][["Location"]]
unmatched_df.to_csv("unmatched_locations.csv", index=False)

# Print Summary & Unmatched List
matched_count = len(df_ref) - len(unmatched_df)
print(f"\nGeocoding Complete: {matched_count} / {len(unique_locations)} locations found.")
print(f"Main outputs written to '{OUTPUT_GEOJSON}' and '{OUTPUT_CSV}'")

if not unmatched_df.empty:
    print(f"\n{len(unmatched_df)} location(s) were NOT found:")
    for loc in unmatched_df["Location"]:
        print(f" - {loc}")
    print("\nSaved missing entries to 'unmatched_locations.csv'.")
else:
    print("\nAll locations were successfully geocoded!")