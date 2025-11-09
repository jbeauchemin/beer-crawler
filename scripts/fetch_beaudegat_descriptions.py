#!/usr/bin/env python3
"""
Script to fetch missing beaudegat descriptions using Selenium.

Reads beers_cleaned.json and fetches descriptions from beaudegat.ca
for beers that have a beaudegat URL but missing/incomplete description.

Usage:
    python scripts/fetch_beaudegat_descriptions.py datas/beers_cleaned.json beers_with_descriptions.json
"""

import json
import sys
import time
import re
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup


class BeaudegatDescriptionFetcher:
    def __init__(self, headless=True):
        """Initialize Selenium WebDriver."""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')

        self.driver = webdriver.Chrome(options=chrome_options)
        print("🌐 Selenium WebDriver initialized (headless Chrome)\n")

    def fetch_description(self, url: str) -> str | None:
        """Fetch beer description from beaudegat website."""
        try:
            self.driver.get(url)
            time.sleep(1.5)  # Shorter delay - same as your crawler

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Find the product description div (note: class is 'product__description rte')
            desc_div = soup.find('div', class_='product__description rte')
            if not desc_div:
                return None

            # Extract all paragraphs
            paragraphs = desc_div.find_all('p')

            if not paragraphs or len(paragraphs) < 3:
                return None

            # Structure of paragraphs:
            # paragraphs[0]: Producer - Alcohol% - Volume ml (metadata)
            # paragraphs[1]: Style like "HOUBLONNÉE"
            # paragraphs[2:]: Actual beer description

            description_parts = []
            for p in paragraphs[2:]:
                text = p.get_text(strip=True)
                if text:
                    description_parts.append(text)

            description = ' '.join(description_parts)
            return description.strip() if description else None

        except Exception as e:
            print(f"  ⚠️  Error fetching {url}: {e}")
            return None

    def needs_description(self, beer: dict) -> tuple[bool, str | None]:
        """
        Check if beer needs a beaudegat description.
        Returns (needs_fetch, beaudegat_url)
        """
        # Get beaudegat description if exists
        descriptions = beer.get('descriptions', {})
        beaudegat_desc = descriptions.get('beaudegat', '')

        # Check if description is missing or incomplete (just metadata)
        needs_fetch = False
        if not beaudegat_desc:
            needs_fetch = True
        elif len(beaudegat_desc) < 50:  # Too short - probably just metadata
            needs_fetch = True
        elif re.match(r'^[^-]+ - \d+\.?\d*% - \d+\s*ml', beaudegat_desc):  # Just metadata line
            needs_fetch = True

        if not needs_fetch:
            return False, None

        # Find beaudegat URL
        urls = beer.get('urls', [])
        for url in urls:
            if 'beaudegat.ca/products/' in url:
                return True, url

        return False, None

    def process_beers(self, input_file: Path, output_file: Path):
        """Process all beers and fetch missing descriptions."""
        print(f"📖 Loading beers from {input_file}...")
        with open(input_file, 'r', encoding='utf-8') as f:
            beers = json.load(f)

        print(f"✂️  Found {len(beers)} beers\n")

        # Count how many need fetching
        to_fetch = []
        for beer in beers:
            needs, url = self.needs_description(beer)
            if needs and url:
                to_fetch.append((beer, url))

        print(f"🔍 Need to fetch {len(to_fetch)} descriptions from beaudegat\n")

        if not to_fetch:
            print("✅ All beers already have good descriptions!")
            return beers

        # Fetch descriptions
        fetched = 0
        failed = 0

        for i, (beer, url) in enumerate(to_fetch, 1):
            beer_name = beer.get('name', 'Unknown')
            print(f"[{i}/{len(to_fetch)}] {beer_name}")
            print(f"  🔗 {url}")

            description = self.fetch_description(url)

            if description:
                # Update the beer's description
                if 'descriptions' not in beer:
                    beer['descriptions'] = {}
                beer['descriptions']['beaudegat'] = description
                fetched += 1
                print(f"  ✓ Fetched: {description[:80]}...")
            else:
                failed += 1
                print(f"  ✗ Failed to fetch description")

            # Save progress incrementally after each beer
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(beers, f, ensure_ascii=False, indent=2)
            print(f"  💾 Progress saved ({i}/{len(to_fetch)})")
            print()

        # Save results
        print(f"💾 Saving updated data to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(beers, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Done!")
        print(f"   Descriptions fetched: {fetched}")
        print(f"   Failed: {failed}")
        print(f"   Total beers: {len(beers)}")

        return beers

    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            print("\n🌐 Selenium WebDriver closed")


def main():
    if len(sys.argv) != 3:
        print("Usage: python fetch_beaudegat_descriptions.py <input.json> <output.json>")
        print("Example: python fetch_beaudegat_descriptions.py beers_cleaned.json beers_with_descriptions.json")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    if not input_file.exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)

    print("🍺 Beaudegat Description Fetcher\n")

    fetcher = BeaudegatDescriptionFetcher(headless=True)

    try:
        fetcher.process_beers(input_file, output_file)
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()
