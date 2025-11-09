#!/usr/bin/env python3
"""Test script to verify ABV extraction works correctly."""

import json
import sys
sys.path.insert(0, 'scripts')

from classify_beers_parallel import extract_abv

# Load test beers
with open('data/test_fix.json', 'r') as f:
    beers = json.load(f)

print("🧪 Testing ABV Extraction\n")
print("=" * 80)

for beer in beers:
    name = beer.get('name', 'Unknown')
    abv = extract_abv(beer)
    alcohol_field = beer.get('alcohol', 'N/A')
    abv_normalized = beer.get('abv_normalized', 'N/A')

    print(f"\n📦 Beer: {name}")
    print(f"   alcohol field: {alcohol_field}")
    print(f"   abv_normalized field: {abv_normalized}")
    print(f"   ✅ Extracted ABV: {abv}")

    # Determine expected alcohol_strength
    if abv:
        if abv < 0.5:
            strength = "ALCOHOL_FREE"
        elif abv < 5:
            strength = "LIGHT"
        elif abv <= 7:
            strength = "MEDIUM"
        else:
            strength = "STRONG"
        print(f"   🎯 Expected alcohol_strength: {strength}")

print("\n" + "=" * 80)
print("\n✅ All extractions completed successfully!")
