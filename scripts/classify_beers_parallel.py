#!/usr/bin/env python3
"""
Parallel beer classification with retry logic and Prisma-ready output.

Features:
- Parallel processing with configurable workers (2-3 recommended)
- Retry failed classifications up to 3 times
- Progress tracking (resume from where you left off)
- Thread-safe incremental saving
- Formats data for Prisma Beer schema
- Same quality as sequential version

Recommended: Use 2 workers on M2 32GB for 2x speed improvement
"""

import json
import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from tqdm import tqdm


# Classification schema
STYLE_CODES = [
    'BLONDE_GOLDEN', 'WHEAT_WITBIER', 'IPA', 'PALE_ALE', 'RED_AMBER',
    'LAGER_PILSNER', 'SAISON_FARMHOUSE', 'SOUR_TART', 'STOUT_PORTER', 'CIDER'
]

FLAVOR_CODES = [
    'HOPPY_BITTER', 'CITRUS_TROPICAL', 'MALTY_GRAINY', 'CARAMEL_TOFFEE_SWEET',
    'CHOCOLATE_COFFEE', 'RED_FRUITS_BERRIES', 'ORCHARD_FRUITS', 'SPICY_HERBAL',
    'WOODY_SMOKY', 'SOUR_TART_FUNKY'
]

BITTERNESS_LEVELS = ['LOW', 'MEDIUM', 'HIGH']
ALCOHOL_STRENGTHS = ['ALCOHOL_FREE', 'LIGHT', 'MEDIUM', 'STRONG']

# Mapping codes to names (for Prisma)
STYLE_NAMES = {
    'BLONDE_GOLDEN': 'Blonde / Golden Ale',
    'WHEAT_WITBIER': 'Wheat Beer / Witbier',
    'IPA': 'IPA',
    'PALE_ALE': 'Pale Ale',
    'RED_AMBER': 'Red Ale / Amber',
    'LAGER_PILSNER': 'Lager / Pilsner',
    'SAISON_FARMHOUSE': 'Saison / Farmhouse Ale',
    'SOUR_TART': 'Sour / Tart Beer',
    'STOUT_PORTER': 'Stout / Porter',
    'CIDER': 'Cider',
}

FLAVOR_NAMES = {
    'HOPPY_BITTER': 'Hoppy / Bitter',
    'CITRUS_TROPICAL': 'Citrus / Tropical',
    'MALTY_GRAINY': 'Malty / Grainy',
    'CARAMEL_TOFFEE_SWEET': 'Caramel / Toffee / Sweet',
    'CHOCOLATE_COFFEE': 'Chocolate / Coffee',
    'RED_FRUITS_BERRIES': 'Red Fruits / Berries',
    'ORCHARD_FRUITS': 'Peach, Pear & Orchard Fruits',
    'SPICY_HERBAL': 'Spicy / Herbal',
    'WOODY_SMOKY': 'Woody / Smoky',
    'SOUR_TART_FUNKY': 'Sour / Tart / Funky',
}


def extract_abv(beer: Dict) -> Optional[float]:
    """Extract ABV from beer data, trying multiple sources."""
    import re

    # Try abv_normalized first (preferred)
    if beer.get('abv_normalized'):
        return float(beer['abv_normalized'])

    # Try direct 'abv' field
    if beer.get('abv'):
        abv_val = beer['abv']
        if isinstance(abv_val, (int, float)):
            return float(abv_val)
        # If it's a string, try to parse it
        if isinstance(abv_val, str):
            match = re.search(r'(\d+\.?\d*)\s*%?', abv_val)
            if match:
                return float(match.group(1))

    # Try 'alcohol' field in rawData (fallback)
    if 'alcohol' in beer:
        alcohol = beer['alcohol']
        if isinstance(alcohol, str):
            match = re.search(r'(\d+\.?\d*)\s*%', alcohol)
            if match:
                return float(match.group(1))

    return None


def build_classification_prompt(beer: Dict) -> str:
    """Build the prompt for LLM classification."""
    name = beer.get('name', 'Unknown')
    producer = beer.get('producer', 'Unknown')
    abv = extract_abv(beer)
    ibu = beer.get('ibu_normalized')

    descriptions = beer.get('descriptions', {})
    desc_text = "\n".join([f"- {source}: {desc}" for source, desc in descriptions.items()])

    styles = beer.get('styles', {})
    styles_text = ", ".join([f"{source}: {style}" for source, style in styles.items()])

    sub_styles = beer.get('sub_styles', {})
    sub_styles_text = ", ".join([f"{source}: {style}" for source, style in sub_styles.items()])

    prompt = f"""You are a passionate beer sommelier with a fun, casual vibe. Analyze this beer and provide classification + awesome descriptions!

🍺 BEER INFO:
Name: {name}
Producer: {producer}
ABV: {abv}% (alcohol by volume)
IBU: {ibu if ibu else 'Unknown'}

Styles mentioned:
{styles_text if styles_text else 'None'}

Sub-styles:
{sub_styles_text if sub_styles_text else 'None'}

Descriptions:
{desc_text if desc_text else 'No description available'}

📋 CLASSIFICATION RULES:

1. style_code - Choose EXACTLY ONE:
{chr(10).join([f'   - {code}' for code in STYLE_CODES])}

2. flavors - Choose 2-3 flavors that BEST represent this beer (minimum 2, maximum 4):
{chr(10).join([f'   - {code}' for code in FLAVOR_CODES])}

   IMPORTANT: Most beers have AT LEAST 2 distinct flavor profiles. Be generous but accurate!
   Examples:
   - Witbier: SPICY_HERBAL (coriander) + CITRUS_TROPICAL (orange peel)
   - IPA: HOPPY_BITTER + CITRUS_TROPICAL
   - Stout: CHOCOLATE_COFFEE + MALTY_GRAINY + CARAMEL_TOFFEE_SWEET

3. bitterness_level - Based on IBU or style:
   - LOW: 0-20 IBU (Wheat, Blonde, Sour, most Lagers)
   - MEDIUM: 20-40 IBU (Pale Ale, Amber, some IPAs)
   - HIGH: 40+ IBU (IPA, Double IPA)

4. alcohol_strength - Based on ABV:
   - ALCOHOL_FREE: 0-0.5%
   - LIGHT: 0.5% to under 5%
   - MEDIUM: 5-7% (inclusive)
   - STRONG: over 7%

5. description_fr - Write a FUN, FRIENDLY French description (2-3 sentences, 50-80 words)

   Make it friendly, funny, and pleasant to read. Use a casual tone like talking to a friend.
   SAFETY RULE: Never reference minors, children, or underage drinking ("mineur", "enfant", "jeune")

6. description_en - Write a FUN, FRIENDLY English description (2-3 sentences, 50-80 words)

   Same: make it casual, fun, and enjoyable to read. Don't be too serious. Think beer blog vibes.
   SAFETY RULE: Never reference minors, children, or underage drinking ("minor", "kid", "youth")

CRITICAL RULES:
- Use ONLY the exact codes provided
- MUST have 2-3 flavors (rarely 1, occasionally 4)
- Descriptions MUST be fun, casual, exciting - NO formal beer-review language!

Respond with ONLY valid JSON:
{{
  "style_code": "...",
  "flavors": ["...", "...", "..."],
  "bitterness_level": "...",
  "alcohol_strength": "...",
  "description_fr": "...",
  "description_en": "..."
}}"""

    return prompt


def call_ollama(prompt: str, model: str = "mixtral:latest", temperature: float = 0.8) -> Optional[Dict]:
    """Call Ollama API to get classification."""
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model,
                'prompt': prompt,
                'stream': False,
                'temperature': temperature,
                'format': 'json',
            },
            timeout=120
        )

        if response.status_code != 200:
            return None

        result = response.json()
        response_text = result.get('response', '').strip()

        try:
            classification = json.loads(response_text)
            return classification
        except json.JSONDecodeError:
            return None

    except requests.exceptions.RequestException:
        return None


def validate_classification(classification: Dict) -> bool:
    """Validate that classification follows the rules."""
    if not classification:
        return False

    required_fields = ['style_code', 'flavors', 'bitterness_level', 'alcohol_strength',
                      'description_fr', 'description_en']
    if not all(field in classification for field in required_fields):
        return False

    if classification['style_code'] not in STYLE_CODES:
        return False

    flavors = classification['flavors']
    if not isinstance(flavors, list) or len(flavors) < 1 or len(flavors) > 4:
        return False

    if not all(f in FLAVOR_CODES for f in flavors):
        return False

    if classification['bitterness_level'] not in BITTERNESS_LEVELS:
        return False

    if classification['alcohol_strength'] not in ALCOHOL_STRENGTHS:
        return False

    return True


def classify_beer_with_retry(beer: Dict, model: str = "mixtral:latest", max_retries: int = 3) -> Optional[Dict]:
    """Classify a beer with retry logic."""
    for attempt in range(max_retries):
        prompt = build_classification_prompt(beer)
        classification = call_ollama(prompt, model)

        if classification and validate_classification(classification):
            return classification

        if attempt < max_retries - 1:
            time.sleep(2)

    return None


def get_first_image(photo_urls: Dict) -> Optional[str]:
    """Get first available image URL."""
    if not photo_urls:
        return None
    for url in photo_urls.values():
        if url:
            return url
    return None


def format_for_prisma(beer: Dict, classification: Optional[Dict]) -> Dict:
    """Format beer data for Prisma schema."""
    # Extract ABV from multiple sources
    abv_value = extract_abv(beer)

    prisma_beer = {
        "codeBar": beer.get('upc') or None,
        "productName": beer.get('name'),
        "abv": str(abv_value) if abv_value else None,
        "ibu": str(beer.get('ibu_normalized')) if beer.get('ibu_normalized') else None,
        "rating": str(beer.get('untappd_rating', 0)),
        "numRatings": beer.get('untappd_rating_count', 0),
        "imageUrl": get_first_image(beer.get('photo_urls', {})),
        "producer": {
            "name": beer.get('producer')
        },
        "rawData": beer
    }

    if classification:
        prisma_beer.update({
            "alcoholStrength": classification['alcohol_strength'],
            "bitternessLevel": classification['bitterness_level'],
            "descriptionFr": classification['description_fr'],
            "descriptionEn": classification['description_en'],
            "style": {
                "code": classification['style_code'],
                "name": STYLE_NAMES[classification['style_code']]
            },
            "flavors": [
                {
                    "code": flavor_code,
                    "name": FLAVOR_NAMES[flavor_code]
                }
                for flavor_code in classification['flavors']
            ]
        })

    return prisma_beer


class ThreadSafeProgress:
    """Thread-safe progress tracking."""
    def __init__(self):
        self.lock = threading.Lock()
        self.classified_beers = []
        self.failed_beers = []
        self.processed_count = 0

    def add_classified(self, beer: Dict):
        with self.lock:
            self.classified_beers.append(beer)
            self.processed_count += 1

    def add_failed(self, beer_info: Dict):
        with self.lock:
            self.failed_beers.append(beer_info)

    def get_stats(self):
        with self.lock:
            return {
                'classified': len(self.classified_beers),
                'failed': len(self.failed_beers),
                'processed': self.processed_count
            }

    def get_all_beers(self):
        with self.lock:
            return self.classified_beers.copy()

    def get_failed(self):
        with self.lock:
            return self.failed_beers.copy()


def process_beer(args):
    """Process a single beer (used by thread pool)."""
    index, beer, model = args
    beer_name = beer.get('name', 'Unknown')

    # Classify with retry
    classification = classify_beer_with_retry(beer, model, max_retries=3)

    # Format for Prisma
    prisma_beer = format_for_prisma(beer, classification)

    return {
        'index': index,
        'beer': prisma_beer,
        'classification': classification,
        'name': beer_name,
        'producer': beer.get('producer'),
        'upc': beer.get('upc')
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python classify_beers_parallel.py <input.json> <output.json> [OPTIONS]")
        print("\nOptions:")
        print("  --model MODEL    Ollama model to use (default: mixtral:latest)")
        print("  --workers N      Number of parallel workers (default: 2, max recommended: 3)")
        print("  --limit N        Only process first N beers (for testing)")
        print("  --resume         Resume from last checkpoint")
        print("\nExample:")
        print("  python classify_beers_parallel.py beers_cleaned.json beers_prisma.json --workers 2")
        print("  python classify_beers_parallel.py beers_cleaned.json beers_prisma.json --workers 3")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    progress_file = output_file.parent / f"{output_file.stem}.progress"

    # Parse arguments
    model = "mixtral:latest"
    workers = 2  # Default: safe for M2 32GB
    limit = None
    resume = False

    for i, arg in enumerate(sys.argv):
        if arg == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]
        elif arg == "--workers" and i + 1 < len(sys.argv):
            workers = int(sys.argv[i + 1])
        elif arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        elif arg == "--resume":
            resume = True

    if not input_file.exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)

    print(f"🍺 Parallel Beer Classification")
    print(f"📖 Input: {input_file}")
    print(f"💾 Output: {output_file}")
    print(f"🤖 Model: {model}")
    print(f"⚡ Workers: {workers}")
    print()

    # Load beers
    print(f"📖 Loading beers...")
    with open(input_file, 'r', encoding='utf-8') as f:
        beers = json.load(f)

    if limit:
        beers = beers[:limit]
        print(f"⚠️  Testing mode: Processing only {limit} beers")

    print(f"✅ Loaded {len(beers)} beers")
    print()

    # Check Ollama
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code != 200:
            print("❌ Error: Ollama is not responding. Make sure 'ollama serve' is running.")
            sys.exit(1)
    except requests.exceptions.RequestException:
        print("❌ Error: Cannot connect to Ollama. Make sure 'ollama serve' is running.")
        sys.exit(1)

    # Thread-safe progress
    progress = ThreadSafeProgress()

    # Process beers in parallel
    print(f"🚀 Starting parallel classification with {workers} workers...")
    print(f"💡 Tip: Each worker processes beers independently for {workers}x speed")
    print()

    # Prepare work items
    work_items = [(i, beer, model) for i, beer in enumerate(beers)]

    # Process with thread pool
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit all jobs
        futures = {executor.submit(process_beer, item): item for item in work_items}

        # Process results as they complete
        with tqdm(total=len(beers), desc="Processing beers") as pbar:
            for future in as_completed(futures):
                result = future.result()

                if result['classification']:
                    progress.add_classified(result['beer'])
                else:
                    progress.add_classified(result['beer'])
                    progress.add_failed({
                        'index': result['index'],
                        'name': result['name'],
                        'producer': result['producer'],
                        'upc': result['upc']
                    })

                pbar.update(1)

                # Save every 10 beers
                stats = progress.get_stats()
                if stats['processed'] % 10 == 0:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(progress.get_all_beers(), f, ensure_ascii=False, indent=2)

    # Final save
    print()
    print(f"💾 Saving final results...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(progress.get_all_beers(), f, ensure_ascii=False, indent=2)

    # Save failed beers
    failed = progress.get_failed()
    if failed:
        failed_file = output_file.parent / f"{output_file.stem}_failed.json"
        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        print(f"⚠️  Failed beers saved to: {failed_file}")

    # Summary
    stats = progress.get_stats()
    print()
    print(f"✅ Classification complete!")
    print(f"   Total beers: {len(beers)}")
    print(f"   Successfully classified: {stats['classified'] - len(failed)}")
    print(f"   Failed: {len(failed)}")
    print(f"   Workers used: {workers}")
    print()
    print(f"📄 Prisma-ready output: {output_file}")


if __name__ == "__main__":
    main()
