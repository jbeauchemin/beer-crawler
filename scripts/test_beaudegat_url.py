#!/usr/bin/env python3
"""
Quick test script to debug a single beaudegat URL.

Usage:
    python scripts/test_beaudegat_url.py "https://beaudegat.ca/products/haze-wars-nano-cinco"
"""

import sys
from fetch_beaudegat_descriptions import BeaudegatDescriptionFetcher

if len(sys.argv) != 2:
    print("Usage: python test_beaudegat_url.py <url>")
    sys.exit(1)

url = sys.argv[1]

print(f"Testing URL: {url}\n")

fetcher = BeaudegatDescriptionFetcher(headless=False, debug=True)

try:
    description = fetcher.fetch_description(url)
    print(f"\n{'='*80}")
    if description:
        print(f"✅ SUCCESS!\n")
        print(f"Description: {description}")
    else:
        print(f"❌ FAILED - No description extracted")
    print(f"{'='*80}")
finally:
    fetcher.close()
