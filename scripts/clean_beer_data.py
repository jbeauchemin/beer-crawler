#!/usr/bin/env python3
"""
Script to clean beer JSON data before LLM classification.

Removes unnecessary fields and prepares data for classification:
- Removes: price, availability, source, pack_info, prices, region, etc.
- Keeps: urls, descriptions, photo_urls, styles, sub_styles for LLM context
- Removes existing classifications to regenerate from scratch
- Fetches missing descriptions from beaudegat website
"""

import json
import sys
import re
import time
import argparse
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

try:
    import requests
    from bs4 import BeautifulSoup
    SCRAPING_AVAILABLE = True
except ImportError:
    SCRAPING_AVAILABLE = False
    print("⚠️  Warning: requests or beautifulsoup4 not installed. Skipping description fetching.")
    print("   Install with: pip install requests beautifulsoup4")

# Global lock for thread-safe printing
print_lock = Lock()

def fetch_beaudegat_description(url: str) -> Optional[str]:
    """Fetch beer description from beaudegat website."""
    if not SCRAPING_AVAILABLE:
        return None

    try:
        # Add delay to be polite to the server
        time.sleep(0.5)

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the product description div
        desc_div = soup.find('div', class_='product__description')
        if not desc_div:
            return None

        # Get text and clean it
        text = desc_div.get_text(separator=' ', strip=True)

        # Remove common patterns that aren't part of the description
        # Remove producer info line (e.g., "Microbrasserie Le Trèfle Noir - 7.0% - 355 ml")
        text = re.sub(r'^[^-]+ - \d+\.?\d*% - \d+\s*ml\s*', '', text)

        # Remove style tags (e.g., "NOIRE", "HOUBLONNÉE")
        text = re.sub(r'^\s*(NOIRE|BLONDE|ROUSSE|BLANCHE|HOUBLONNÉE|SOIF|SÛRE|COMPLEXE)\s*', '', text, flags=re.IGNORECASE)

        # Clean up whitespace
        text = ' '.join(text.split())

        return text.strip() if text else None

    except Exception as e:
        print(f"⚠️  Failed to fetch description from {url}: {e}")
        return None


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

    # If no descriptions and we have a beaudegat URL, try to fetch it
    if not descriptions and SCRAPING_AVAILABLE:
        beaudegat_url = None

        # Check if there's a beaudegat URL in urls list
        urls = beer.get("urls", [])
        if isinstance(urls, list):
            for url in urls:
                if "beaudegat.ca" in url:
                    beaudegat_url = url
                    break

        # Or check if there's a single url field
        if not beaudegat_url and beer.get("url") and "beaudegat.ca" in beer.get("url", ""):
            beaudegat_url = beer["url"]

        # Fetch description from beaudegat
        if beaudegat_url:
            fetched_desc = fetch_beaudegat_description(beaudegat_url)
            if fetched_desc:
                descriptions["beaudegat"] = fetched_desc
                with print_lock:
                    print(f"  ✓ Fetched description for {beer.get('name')}")

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
    parser = argparse.ArgumentParser(
        description='Clean beer JSON data before LLM classification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Sequential processing (default)
  python clean_beer_data.py input.json output.json

  # Parallel processing with 5 workers
  python clean_beer_data.py input.json output.json --workers 5

  # Parallel processing with 10 workers (faster for large datasets)
  python clean_beer_data.py input.json output.json -w 10
        '''
    )
    parser.add_argument('input_file', type=Path, help='Input JSON file')
    parser.add_argument('output_file', type=Path, help='Output JSON file')
    parser.add_argument('-w', '--workers', type=int, default=1,
                        help='Number of parallel workers (default: 1 = sequential)')

    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"❌ Error: Input file '{args.input_file}' not found")
        sys.exit(1)

    print(f"📖 Loading beers from {args.input_file}...")
    with open(args.input_file, 'r', encoding='utf-8') as f:
        beers = json.load(f)

    print(f"✂️  Cleaning {len(beers)} beers...")

    if args.workers > 1:
        print(f"🚀 Using {args.workers} parallel workers")
        cleaned_beers = []

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            # Submit all jobs
            future_to_beer = {executor.submit(clean_beer_entry, beer): i
                             for i, beer in enumerate(beers)}

            # Collect results as they complete
            results = [None] * len(beers)
            completed = 0

            for future in as_completed(future_to_beer):
                idx = future_to_beer[future]
                try:
                    results[idx] = future.result()
                    completed += 1
                    if completed % 100 == 0:
                        with print_lock:
                            print(f"  Progress: {completed}/{len(beers)} beers processed")
                except Exception as e:
                    with print_lock:
                        print(f"⚠️  Error processing beer {idx}: {e}")
                    results[idx] = None

            cleaned_beers = [r for r in results if r is not None]
    else:
        # Sequential processing
        cleaned_beers = []
        for i, beer in enumerate(beers):
            cleaned_beers.append(clean_beer_entry(beer))
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i + 1}/{len(beers)} beers processed")

    print(f"💾 Saving cleaned data to {args.output_file}...")
    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_beers, f, ensure_ascii=False, indent=2)

    # Calculate size reduction
    input_size = args.input_file.stat().st_size / 1024 / 1024  # MB
    output_size = args.output_file.stat().st_size / 1024 / 1024  # MB
    reduction = ((input_size - output_size) / input_size) * 100

    print(f"\n✅ Done!")
    print(f"   Original: {input_size:.2f} MB")
    print(f"   Cleaned:  {output_size:.2f} MB")
    print(f"   Reduction: {reduction:.1f}%")
    print(f"   Beers processed: {len(cleaned_beers)}")


if __name__ == "__main__":
    main()
