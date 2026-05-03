"""
Horse Finder - Data Analysis Script
=====================================
This script reads Horses_for_sale.csv, cleans and analyzes the data,
and outputs horses_data.json for use by the website UI.

Usage:
    python analyze_horses.py

Output:
    horses_data.json  — structured data for the web interface
"""

import pandas as pd
import json
import re
from collections import Counter


# ── 1. LOAD DATA ─────────────────────────────────────────────────────────────

print("Loading data...")
df = pd.read_csv("Horses_for_sale.csv")
print(f"  Raw rows: {len(df):,}  |  Columns: {list(df.columns)}")


# ── 2. CLEAN & TRANSFORM ─────────────────────────────────────────────────────

# Parse $ Price -> numeric
df["price_num"] = (
    df["$ Price"]
    .astype(str)
    .str.replace(r"[\$,]", "", regex=True)
    .str.strip()
    .pipe(pd.to_numeric, errors="coerce")
)

# Parse Age -> integer years
df["age_num"] = (
    df["Age"]
    .astype(str)
    .str.extract(r"(\d+)")[0]
    .pipe(pd.to_numeric, errors="coerce")
)

# Parse Height (hh) -> float  e.g. "15,2 hh" -> 15.2
df["height_num"] = (
    df["Height"]
    .astype(str)
    .str.replace(",", ".", regex=False)
    .str.replace(r"\s*hh", "", regex=True)
    .str.strip()
    .pipe(pd.to_numeric, errors="coerce")
)

# Drop rows missing essential fields
df_clean = df.dropna(subset=["Breed", "Gender"]).copy()
print(f"  Clean rows (breed+gender present): {len(df_clean):,}")


# ── 3. DATA TRANSFORMATIONS ───────────────────────────────────────────────────

# --- Breed: strip " Mix" suffix
def clean_breed(breed):
    if not isinstance(breed, str):
        return breed
    return re.sub(r'\s+Mix$', '', breed.strip(), flags=re.IGNORECASE)

df_clean["breed_clean"] = df_clean["Breed"].apply(clean_breed)
mix_count = (df_clean["Breed"] != df_clean["breed_clean"]).sum()
print(f"\n  Breed 'Mix' suffix removed from {mix_count:,} horses")

# --- Color: consolidate similar colors
COLOR_MAP = {
    "Sorrel":          "Chestnut",
    "Chestnut-Red":    "Chestnut",
    "Brown-Light":     "Brown",
    "Gray-Blue-Tan":   "Gray",
    "Gray-Dark-Tan":   "Gray",
    "Gray-Red-Tan":    "Gray",
    "Gray-Fleabitten": "Gray",
    "Gray-Dapple":     "Gray",
    "Can be white":    "Albino",
    "White":           "Albino",
}

def clean_color(color):
    if not isinstance(color, str):
        return color
    return COLOR_MAP.get(color.strip(), color.strip())

color_changes = sum(
    1 for _, row in df_clean.iterrows()
    if pd.notna(row["Color"]) and row["Color"].strip() in COLOR_MAP
)
print(f"  Color consolidations applied to {color_changes:,} horses")


# ── 4. SUMMARY STATISTICS ────────────────────────────────────────────────────

print("\n-- SUMMARY STATISTICS --")

print(f"\nBreed (top 10, after cleaning):")
for breed, cnt in df_clean["breed_clean"].value_counts().head(10).items():
    print(f"  {breed:<40} {cnt:>5}")

print(f"\nColor distribution (after cleaning):")
for color, cnt in df_clean["Color"].apply(clean_color).value_counts().items():
    print(f"  {color:<30} {cnt:>5}")

print(f"\nGender distribution:")
for g, cnt in df_clean["Gender"].value_counts().items():
    print(f"  {g:<15} {cnt:>5}")

print(f"\nAge range: {df_clean['age_num'].min():.0f} - {df_clean['age_num'].max():.0f} years")
print(f"Height range: {df_clean['height_num'].min():.1f} - {df_clean['height_num'].max():.1f} hh")

prices = df_clean["price_num"].dropna()
print(f"\nPrice stats (USD):")
print(f"  Min:    ${prices.min():>12,.0f}")
print(f"  Median: ${prices.median():>12,.0f}")
print(f"  Mean:   ${prices.mean():>12,.0f}")
print(f"  Max:    ${prices.max():>12,.0f}")

all_disciplines = set()
for d in df_clean["Discipline"].dropna():
    for part in d.split(" - "):
        s = part.strip()
        if s:
            all_disciplines.add(s)
print(f"\nUnique disciplines ({len(all_disciplines)}): {sorted(all_disciplines)}")


# ── 5. BUILD JSON RECORDS ────────────────────────────────────────────────────

def safe_str(val):
    return str(val).strip() if pd.notna(val) else None

def parse_list(val, sep=","):
    if not val or not isinstance(val, str):
        return []
    return [x.strip() for x in val.split(sep) if x.strip() and x.strip() != "end"]

def is_pony_or_miniature(breed):
    if not isinstance(breed, str):
        return False
    b = breed.lower()
    return "pony" in b or "miniature" in b or "ponies" in b

RIDER_WARNING = "May not be suitable for young riders"

records = []
pony_warning_count = 0
stallion_warning_count = 0

for _, row in df_clean.iterrows():
    breed = str(row["breed_clean"]).strip()
    disciplines = parse_list(row["Discipline"], " - ") if pd.notna(row["Discipline"]) else []
    characteristics = parse_list(row["Further Characteristics"], ",") if pd.notna(row["Further Characteristics"]) else []

    # Add rider warning for pony/miniature breeds
    if is_pony_or_miniature(breed):
        if RIDER_WARNING not in characteristics:
            characteristics.append(RIDER_WARNING)
            pony_warning_count += 1

    # Add inexperienced owner warning for young stallions
    age = int(row["age_num"]) if pd.notna(row["age_num"]) else None
    if safe_str(row["Gender"]) == "Stallion" and age is not None and age < 3:
        STALLION_WARNING = "May not be suitable for inexperienced owners"
        if STALLION_WARNING not in characteristics:
            characteristics.append(STALLION_WARNING)
            stallion_warning_count += 1

    records.append({
        "id": int(row["Horse ID"]) if pd.notna(row["Horse ID"]) else None,
        "breed": breed,
        "gender": safe_str(row["Gender"]),
        "age": int(row["age_num"]) if pd.notna(row["age_num"]) else None,
        "height": round(float(row["height_num"]), 1) if pd.notna(row["height_num"]) else None,
        "color": clean_color(row["Color"]) if pd.notna(row["Color"]) else None,
        "location": safe_str(row["Location"]) if pd.notna(row["Location"]) else None,
        "price": float(row["price_num"]) if pd.notna(row["price_num"]) else None,
        "disciplines": disciplines,
        "characteristics": characteristics,
    })

print(f"\n  Rider warning added to {pony_warning_count:,} pony/miniature horses")
print(f"  Inexperienced owner warning added to {stallion_warning_count:,} young stallions")
print(f"  Total records for export: {len(records):,}")


# ── 6. BUILD FILTER METADATA ─────────────────────────────────────────────────

breeds             = sorted(set(r["breed"] for r in records if r["breed"]))
genders            = sorted(set(r["gender"] for r in records if r["gender"]))
colors             = sorted(set(r["color"] for r in records if r["color"]))
disciplines_sorted = sorted(all_disciplines)

price_percentiles = {
    "p25": round(float(prices.quantile(0.25))),
    "p50": round(float(prices.median())),
    "p75": round(float(prices.quantile(0.75))),
    "max": round(float(prices.max())),
}

metadata = {
    "total_horses": len(records),
    "breeds": breeds,
    "genders": genders,
    "colors": colors,
    "disciplines": disciplines_sorted,
    "age_range": [int(df_clean["age_num"].min()), int(df_clean["age_num"].max())],
    "height_range": [
        round(float(df_clean["height_num"].min()), 1),
        round(float(df_clean["height_num"].max()), 1),
    ],
    "price_range": [0, round(float(prices.quantile(0.99)))],
    "price_percentiles": price_percentiles,
}


# ── 7. SAVE OUTPUT ────────────────────────────────────────────────────────────

output = {
    "metadata": metadata,
    "horses": records,
}

with open("horses_data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

size_kb = len(json.dumps(output)) / 1024
print(f"\nSaved horses_data.json  ({size_kb:,.0f} KB, {len(records):,} horses)")
print("Ready to open index.html in a browser.")
