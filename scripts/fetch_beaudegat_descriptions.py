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
    def __init__(self, headless=True, debug=False):
        """Initialize Selenium WebDriver."""
        self.debug = debug
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
                if self.debug:
                    print(f"  🔍 DEBUG: No div with class 'product__description rte' found")
                return None

            # Extract all paragraphs AND divs (some descriptions are in divs, not p tags)
            paragraphs = desc_div.find_all('p')
            content_divs = desc_div.find_all('div', recursive=False)  # Direct child divs only

            if self.debug:
                print(f"  🔍 DEBUG: Found {len(paragraphs)} paragraphs and {len(content_divs)} divs")
                for i, p in enumerate(paragraphs):
                    text = p.get_text(strip=True)
                    print(f"  🔍 DEBUG: Paragraph {i}: {text[:100]}")
                for i, d in enumerate(content_divs):
                    text = d.get_text(strip=True)
                    if text:  # Only show non-empty divs
                        print(f"  🔍 DEBUG: Div {i}: {text[:100]}")

            # Collect all text parts, skipping metadata and style tags
            description_parts = []
            text_to_skip = []  # Track text from metadata/style paragraphs to skip

            # Process paragraphs (skip metadata and style-only paragraphs)
            for i, p in enumerate(paragraphs):
                text = p.get_text(strip=True)

                # Skip metadata paragraphs (contain both % and ml - any order)
                if re.search(r'\d+\.?\d*\s*%', text, re.IGNORECASE) and re.search(r'\d+\s*ml', text, re.IGNORECASE):
                    if self.debug:
                        print(f"  🔍 DEBUG: Skipping metadata paragraph: {text[:80]}")
                    text_to_skip.append(text)
                    continue

                # Skip style-only paragraphs (HOUBLONNÉE, BLONDE, etc.)
                if re.match(r'^.*?(NOIRE|BLONDE|ROUSSE|BLANCHE|HOUBLONNÉE|SOIF|SÛRE|COMPLEXE)\s*$', text, re.IGNORECASE):
                    if self.debug:
                        print(f"  🔍 DEBUG: Skipping style paragraph: {text[:80]}")
                    text_to_skip.append(text)
                    continue

                # Skip very short text
                if len(text) > 20:
                    description_parts.append(text)

            # Process content divs (these often contain the actual description)
            for div in content_divs:
                text = div.get_text(strip=True)

                # Skip divs with metadata (contain both % and ml)
                if re.search(r'\d+\.?\d*\s*%', text, re.IGNORECASE) and re.search(r'\d+\s*ml', text, re.IGNORECASE):
                    if self.debug:
                        print(f"  🔍 DEBUG: Skipping metadata div: {text[:80]}")
                    continue

                if text and len(text) > 20:
                    description_parts.append(text)

            # If no description parts found, try to extract direct text from desc_div
            # (some pages have description as direct text, not in p or div tags)
            if not description_parts:
                if self.debug:
                    print(f"  🔍 DEBUG: No p/div content found, trying to extract direct text from desc_div")

                # Get all text from desc_div
                full_text = desc_div.get_text(separator=' ', strip=True)

                # Remove metadata line at the beginning (everything up to and including ml or %)
                # Pattern: anything ending with "% - XXXml" or "XXXml - X%"
                # We want to remove everything up to the last "ml" in the first sentence
                full_text = re.sub(r'^.*?\d+\s*ml\s*', '', full_text, count=1, flags=re.IGNORECASE)

                # If that didn't work (no ml found), try removing up to %
                if re.search(r'^\s*\d+\.?\d*\s*%', full_text, re.IGNORECASE):
                    full_text = re.sub(r'^.*?\d+\.?\d*\s*%\s*', '', full_text, count=1, flags=re.IGNORECASE)

                # Clean up whitespace
                full_text = ' '.join(full_text.split()).strip()

                if self.debug:
                    print(f"  🔍 DEBUG: Extracted direct text after cleanup: {full_text[:100]}")

                if len(full_text) > 20:
                    description_parts.append(full_text)

            if not description_parts:
                if self.debug:
                    print(f"  🔍 DEBUG: No description parts found")
                return None

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
