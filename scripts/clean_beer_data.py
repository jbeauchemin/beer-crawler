#!/usr/bin/env python3
"""
Script to clean beer JSON data before LLM classification.

Removes unnecessary fields and prepares data for classification:
- Removes: price, availability, source, pack_info, prices, region, etc.
- Keeps: urls, descriptions, photo_urls, styles, sub_styles for LLM context
- Removes existing classifications to regenerate from scratch
"""

import json
import sys
from pathlib import Path


def clean_beer_entry(beer):
    """Clean a single beer entry, removing unnecessary fields."""

    # Build photo_urls from all available image sources
    photo_urls = beer.get("photo_urls", {}).copy()

    # Add photo_url if available and not already in photo_urls
    if beer.get("photo_url") and not any(beer["photo_url"] == url for url in photo_urls.values()):
        source = beer.get("source", "unknown")
        photo_urls[source] = beer["photo_url"]

    # Add untappd_label if available and not a default placeholder
    if beer.get("untappd_label"):
        label_url = beer["untappd_label"]
        # Filter out Untappd default images
        if "badge-beer-default" not in label_url and "temp/" not in label_url:
            photo_urls["untappd"] = label_url

    # Filter out any placeholder images
    photo_urls = {k: v for k, v in photo_urls.items()
                  if v and "placeholder" not in v.lower()}

    # Build descriptions from all available sources
    descriptions = beer.get("descriptions", {}).copy()

    # Add description (singular) if available and not already in descriptions
    if beer.get("description") and not any(beer["description"] == desc for desc in descriptions.values()):
        source = beer.get("source", "unknown")
        descriptions[source] = beer["description"]

    # Build styles from all available sources
    styles = beer.get("styles", {}).copy()

    # Add style (singular) if available and not already in styles
    if beer.get("style") and not any(beer["style"] == s for s in styles.values()):
        source = beer.get("source", "unknown")
        styles[source] = beer["style"]

    # Fields to keep for LLM context
    cleaned = {
        "name": beer.get("name"),
        "producer": beer.get("producer"),
        "alcohol": beer.get("alcohol"),
        "volume": beer.get("volume"),
        "sources": beer.get("sources", []),
        "urls": beer.get("urls", []),
        "descriptions": descriptions,
        "photo_urls": photo_urls,
        "styles": styles,
        "sub_styles": beer.get("sub_styles", {}),
        "upc": beer.get("upc"),
        "untappd_rating": beer.get("untappd_rating"),
        "untappd_rating_count": beer.get("untappd_rating_count"),
    }

    # Extract ABV for classification
    if beer.get("abv_normalized"):
        cleaned["abv_normalized"] = beer["abv_normalized"]
    elif beer.get("untappd_abv"):
        cleaned["abv_normalized"] = beer["untappd_abv"]

    # Extract IBU for classification (if available)
    if beer.get("ibu_normalized"):
        cleaned["ibu_normalized"] = beer["ibu_normalized"]
    elif beer.get("untappd_ibu"):
        cleaned["ibu_normalized"] = beer["untappd_ibu"]

    # Remove None/null values
    return {k: v for k, v in cleaned.items() if v is not None}


def main():
    if len(sys.argv) != 3:
        print("Usage: python clean_beer_data.py <input.json> <output.json>")
        print("Example: python clean_beer_data.py beers_json_perfect_v6.json beers_cleaned.json")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    if not input_file.exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)

    print(f"📖 Loading beers from {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        beers = json.load(f)

    print(f"✂️  Cleaning {len(beers)} beers...")
    cleaned_beers = [clean_beer_entry(beer) for beer in beers]

    print(f"💾 Saving cleaned data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_beers, f, ensure_ascii=False, indent=2)

    # Calculate size reduction
    input_size = input_file.stat().st_size / 1024 / 1024  # MB
    output_size = output_file.stat().st_size / 1024 / 1024  # MB
    reduction = ((input_size - output_size) / input_size) * 100

    print(f"\n✅ Done!")
    print(f"   Original: {input_size:.2f} MB")
    print(f"   Cleaned:  {output_size:.2f} MB")
    print(f"   Reduction: {reduction:.1f}%")
    print(f"   Beers processed: {len(cleaned_beers)}")


if __name__ == "__main__":
    main()
