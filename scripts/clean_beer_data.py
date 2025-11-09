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
    # Create a session to maintain cookies
    SESSION = requests.Session()
except ImportError:
    SCRAPING_AVAILABLE = False
    SESSION = None
    print("⚠️  Warning: requests or beautifulsoup4 not installed. Skipping description fetching.")
    print("   Install with: pip install requests beautifulsoup4")

# Try to import Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
    DRIVER = None  # Will be initialized when needed
except ImportError:
    SELENIUM_AVAILABLE = False
    DRIVER = None

# Global lock for thread-safe printing
print_lock = Lock()

# Global delay between requests (can be overridden via CLI)
REQUEST_DELAY = 2.0
SKIP_FETCH = False
USE_SELENIUM = False

def init_selenium_driver():
    """Initialize Selenium WebDriver (headless Chrome)."""
    global DRIVER
    if DRIVER is None and SELENIUM_AVAILABLE:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        DRIVER = webdriver.Chrome(options=chrome_options)
        with print_lock:
            print("🌐 Selenium WebDriver initialized (headless Chrome)")
    return DRIVER


def fetch_with_selenium(url: str) -> Optional[str]:
    """Fetch description using Selenium (bypasses anti-bot)."""
    global DRIVER

    if DRIVER is None:
        DRIVER = init_selenium_driver()

    if DRIVER is None:
        return None

    try:
        time.sleep(REQUEST_DELAY)
        DRIVER.get(url)
        time.sleep(2)  # Wait for page to load

        soup = BeautifulSoup(DRIVER.page_source, 'html.parser')

        # Find the product description div
        desc_div = soup.find('div', class_='product__description')
        if not desc_div:
            return None

        # Extract text from paragraphs (skip first line and style tags)
        paragraphs = desc_div.find_all('p')
        description_parts = []

        for p in paragraphs:
            text = p.get_text(strip=True)
            # Skip paragraphs with style tags only (NOIRE, BLONDE, etc.)
            if text and not re.match(r'^(NOIRE|BLONDE|ROUSSE|BLANCHE|HOUBLONNÉE|SOIF|SÛRE|COMPLEXE)$', text, re.IGNORECASE):
                # Skip meta tags and very short text
                if len(text) > 20:
                    description_parts.append(text)

        # If no paragraphs found, try getting all text
        if not description_parts:
            text = desc_div.get_text(separator=' ', strip=True)
            # Remove producer info line (various formats)
            text = re.sub(r'^[^-]+\d+\.?\d*\s*%[^A-Z]*', '', text)
            text = re.sub(r'^\s*(NOIRE|BLONDE|ROUSSE|BLANCHE|HOUBLONNÉE|SOIF|SÛRE|COMPLEXE)\s*', '', text, flags=re.IGNORECASE)
            text = ' '.join(text.split())
            return text.strip() if text else None

        return ' '.join(description_parts).strip()

    except Exception as e:
        with print_lock:
            print(f"⚠️  Selenium error for {url}: {e}")
        return None


def fetch_beaudegat_description(url: str, max_retries: int = 3) -> Optional[str]:
    """Fetch beer description from beaudegat website with retry logic."""
    if SKIP_FETCH:
        return None

    # Use Selenium if enabled and available
    if USE_SELENIUM:
        if not SELENIUM_AVAILABLE:
            with print_lock:
                print("⚠️  Selenium not available. Install with: pip install selenium")
            return None
        return fetch_with_selenium(url)

    # Otherwise use requests (original method)
    if not SCRAPING_AVAILABLE:
        return None

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'fr-CA,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }

    for attempt in range(max_retries):
        try:
            time.sleep(REQUEST_DELAY)
            response = SESSION.get(url, headers=headers, timeout=10)

            if response.status_code == 429:
                wait_time = 5 * (2 ** attempt)
                with print_lock:
                    print(f"⏳ Rate limited. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            desc_div = soup.find('div', class_='product__description')
            if not desc_div:
                return None

            # Extract text from paragraphs (skip first line and style tags)
            paragraphs = desc_div.find_all('p')
            description_parts = []

            for p in paragraphs:
                text = p.get_text(strip=True)
                # Skip paragraphs with style tags only (NOIRE, BLONDE, etc.)
                if text and not re.match(r'^(NOIRE|BLONDE|ROUSSE|BLANCHE|HOUBLONNÉE|SOIF|SÛRE|COMPLEXE)$', text, re.IGNORECASE):
                    # Skip meta tags and very short text
                    if len(text) > 20:
                        description_parts.append(text)

            # If no paragraphs found, try getting all text
            if not description_parts:
                text = desc_div.get_text(separator=' ', strip=True)
                # Remove producer info line (various formats)
                text = re.sub(r'^[^-]+\d+\.?\d*\s*%[^A-Z]*', '', text)
                text = re.sub(r'^\s*(NOIRE|BLONDE|ROUSSE|BLANCHE|HOUBLONNÉE|SOIF|SÛRE|COMPLEXE)\s*', '', text, flags=re.IGNORECASE)
                text = ' '.join(text.split())
                return text.strip() if text else None

            return ' '.join(description_parts).strip()

        except requests.exceptions.HTTPError as e:
            if attempt == max_retries - 1:
                with print_lock:
                    print(f"⚠️  Failed to fetch description from {url} after {max_retries} attempts: {e}")
            continue
        except Exception as e:
            with print_lock:
                print(f"⚠️  Error fetching description from {url}: {e}")
            return None

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

    # If NO beaudegat description and we have a beaudegat URL, try to fetch it
    if "beaudegat" not in descriptions and SCRAPING_AVAILABLE:
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

    # Build URLs list from all available sources
    urls_list = beer.get("urls", [])
    if not isinstance(urls_list, list):
        urls_list = []
    else:
        urls_list = list(urls_list)  # Make a copy

    # Add url (singular) if available and not already in urls
    if beer.get("url") and beer["url"] not in urls_list:
        urls_list.append(beer["url"])

    # Add untappd_url if available and not already in urls
    if beer.get("untappd_url") and beer["untappd_url"] not in urls_list:
        urls_list.append(beer["untappd_url"])

    # Fields to keep for LLM context
    cleaned = {
        "name": beer.get("name"),
        "producer": beer.get("producer"),
        "alcohol": beer.get("alcohol"),
        "volume": beer.get("volume"),
        "sources": beer.get("sources", []),
        "urls": urls_list,
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

  # Skip web fetching (fastest, uses only existing data)
  python clean_beer_data.py input.json output.json --skip-fetch

  # Use Selenium to bypass anti-bot protection (slower but works)
  python clean_beer_data.py input.json output.json --use-selenium

  # Parallel processing with Selenium (NOT recommended - use sequential)
  python clean_beer_data.py input.json output.json --use-selenium -w 1
        '''
    )
    parser.add_argument('input_file', type=Path, help='Input JSON file')
    parser.add_argument('output_file', type=Path, help='Output JSON file')
    parser.add_argument('-w', '--workers', type=int, default=1,
                        help='Number of parallel workers (default: 1 = sequential)')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='Delay between web requests in seconds (default: 2.0)')
    parser.add_argument('--skip-fetch', action='store_true',
                        help='Skip fetching missing descriptions from web (faster, but some beers may lack descriptions)')
    parser.add_argument('--use-selenium', action='store_true',
                        help='Use Selenium WebDriver to bypass anti-bot protection (requires: pip install selenium)')

    args = parser.parse_args()

    # Set global flags
    global REQUEST_DELAY, SKIP_FETCH, USE_SELENIUM
    REQUEST_DELAY = args.delay
    SKIP_FETCH = args.skip_fetch
    USE_SELENIUM = args.use_selenium

    if not args.input_file.exists():
        print(f"❌ Error: Input file '{args.input_file}' not found")
        sys.exit(1)

    print(f"📖 Loading beers from {args.input_file}...")
    if args.skip_fetch:
        print(f"⚠️  Web fetching disabled (--skip-fetch)")
    elif args.use_selenium:
        print(f"🌐 Using Selenium WebDriver (bypasses anti-bot)")
        if args.delay != 2.0:
            print(f"⏱️  Request delay: {args.delay}s")
    elif args.delay != 2.0:
        print(f"⏱️  Request delay: {args.delay}s")
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

    # Cleanup Selenium driver
    global DRIVER
    if DRIVER is not None:
        try:
            DRIVER.quit()
            print("🌐 Selenium WebDriver closed")
        except Exception:
            pass


if __name__ == "__main__":
    main()
