#!/usr/bin/env python3
"""
Beer classification script with retry logic and Prisma-ready output.

Features:
- Retry failed classifications up to 3 times
- Progress tracking (resume from where you left off)
- Incremental saving every 10 beers
- Formats data for Prisma Beer schema
- Detailed logging
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from decimal import Decimal
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

    # If this is a Prisma-formatted beer, get the original from rawData
    original_beer = beer.get('rawData', beer)

    # Try abv_normalized first (preferred)
    if original_beer.get('abv_normalized'):
        return float(original_beer['abv_normalized'])

    # Try direct 'abv' field (could be string from Prisma format)
    if beer.get('abv'):
        abv_val = beer['abv']
        if isinstance(abv_val, (int, float)):
            return float(abv_val)
        # If it's a string, try to parse it
        if isinstance(abv_val, str) and abv_val != 'null':
            match = re.search(r'(\d+\.?\d*)\s*%?', abv_val)
            if match:
                return float(match.group(1))

    # Try 'alcohol' field
    if 'alcohol' in original_beer:
        alcohol = original_beer['alcohol']
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

4. alcohol_strength - Based on ABV (FOLLOW THESE RULES EXACTLY):
   - ALCOHOL_FREE: 0-0.5%
   - LIGHT: 0.5% to 4.9% (examples: 3.5%, 4.2%, 4.8%)
   - MEDIUM: 5.0% to 7.0% (examples: 5.0%, 5.3%, 5.5%, 6.2%, 6.5%, 7.0%)
   - STRONG: over 7.0% (examples: 7.5%, 8.0%, 10.0%)

   IMPORTANT: 5.0% and above = MEDIUM or STRONG, NOT LIGHT!

5. description_fr - Write a FUN, FRIENDLY French description (2-3 sentences, 50-80 words)
   Make it friendly, funny, and pleasant to read. Use a casual tone like talking to a friend.
   SAFETY RULE: Never reference minors, children, or underage drinking ("mineur", "enfant", "jeune")

6. description_en - Write a FUN, FRIENDLY English description (2-3 sentences, 50-80 words)
   Same: make it casual, fun, and enjoyable to read. Don't be too serious. Think beer blog vibes.
   SAFETY RULE: Never reference minors, children, or underage drinking ("minor", "kid", "youth")

CRITICAL RULES:
- Use ONLY the exact codes provided
- MUST have 2-3 flavors (rarely 1, occasionally 4)

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
            time.sleep(2)  # Wait 2 seconds before retry

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

    # Base beer data
    prisma_beer = {
        "codeBar": beer.get('upc') or None,  # Can be null
        "productName": beer.get('name'),
        "abv": str(abv_value) if abv_value else None,
        "ibu": str(beer.get('ibu_normalized')) if beer.get('ibu_normalized') else None,
        "rating": str(beer.get('untappd_rating', 0)),
        "numRatings": beer.get('untappd_rating_count', 0),
        "imageUrl": get_first_image(beer.get('photo_urls', {})),
        "producer": {
            "name": beer.get('producer')
        },
        "rawData": beer  # Store all original data
    }

    # Add classification if available
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


def load_progress(progress_file: Path) -> Dict:
    """Load progress from file."""
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {"last_index": -1, "processed": 0, "failed": []}


def save_progress(progress_file: Path, progress: Dict):
    """Save progress to file."""
    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2)


def main():
    if len(sys.argv) < 3:
        print("Usage: python classify_beers_with_retry.py <input.json> <output.json> [--model MODEL] [--limit N] [--resume]")
        print("\nOptions:")
        print("  --model MODEL    Ollama model to use (default: mixtral:latest)")
        print("  --limit N        Only process first N beers (for testing)")
        print("  --resume         Resume from last checkpoint")
        print("\nExample:")
        print("  python classify_beers_with_retry.py beers_cleaned.json beers_prisma.json")
        print("  python classify_beers_with_retry.py beers_cleaned.json beers_prisma.json --resume")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    progress_file = output_file.parent / f"{output_file.stem}.progress"

    # Parse arguments
    model = "mixtral:latest"
    limit = None
    resume = False

    for i, arg in enumerate(sys.argv):
        if arg == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]
        elif arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        elif arg == "--resume":
            resume = True

    if not input_file.exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)

    print(f"🍺 Beer Classification with Retry & Prisma Format")
    print(f"📖 Input: {input_file}")
    print(f"💾 Output: {output_file}")
    print(f"🤖 Model: {model}")
    print()

    # Load beers
    print(f"📖 Loading beers...")
    with open(input_file, 'r', encoding='utf-8') as f:
        beers = json.load(f)

    # Load existing output if resuming
    classified_beers = []
    if resume and output_file.exists():
        print(f"📂 Loading existing output...")
        with open(output_file, 'r', encoding='utf-8') as f:
            classified_beers = json.load(f)

    # Load progress
    progress = load_progress(progress_file)
    start_index = progress['last_index'] + 1 if resume else 0

    if limit:
        beers = beers[:limit]
        print(f"⚠️  Testing mode: Processing only {limit} beers")

    if resume:
        print(f"📍 Resuming from beer #{start_index}")
        print(f"✅ Already processed: {len(classified_beers)} beers")

    print(f"🔢 Total to process: {len(beers) - start_index}")
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

    # Process beers
    failed_beers = progress.get('failed', [])

    print(f"🚀 Starting classification...")
    print()

    for i in range(start_index, len(beers)):
        beer = beers[i]
        beer_name = beer.get('name', 'Unknown')

        print(f"[{i+1}/{len(beers)}] Classifying: {beer_name}...")

        # Classify with retry
        classification = classify_beer_with_retry(beer, model, max_retries=3)

        if classification:
            print(f"  ✅ Success: {classification['style_code']}, {len(classification['flavors'])} flavors")
        else:
            print(f"  ❌ Failed after 3 retries")
            failed_beers.append({
                'index': i,
                'name': beer_name,
                'producer': beer.get('producer'),
                'upc': beer.get('upc')
            })

        # Format for Prisma
        prisma_beer = format_for_prisma(beer, classification)
        classified_beers.append(prisma_beer)

        # Update progress
        progress['last_index'] = i
        progress['processed'] = len(classified_beers)
        progress['failed'] = failed_beers

        # Save every 10 beers
        if (i + 1) % 10 == 0 or i == len(beers) - 1:
            print(f"  💾 Saving progress... ({len(classified_beers)} beers)")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(classified_beers, f, ensure_ascii=False, indent=2)
            save_progress(progress_file, progress)

    # Final save
    print()
    print(f"💾 Saving final results...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(classified_beers, f, ensure_ascii=False, indent=2)

    # Save failed beers
    if failed_beers:
        failed_file = output_file.parent / f"{output_file.stem}_failed.json"
        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump(failed_beers, f, ensure_ascii=False, indent=2)
        print(f"⚠️  Failed beers saved to: {failed_file}")

    # Summary
    print()
    print(f"✅ Classification complete!")
    print(f"   Total beers: {len(beers)}")
    print(f"   Successfully classified: {len(classified_beers) - len(failed_beers)}")
    print(f"   Failed: {len(failed_beers)}")
    print()
    print(f"📄 Prisma-ready output: {output_file}")
    print()
    print(f"💡 Next steps:")
    print(f"   - Review the output in {output_file}")
    print(f"   - Use this data to upsert into your Prisma database")
    if failed_beers:
        print(f"   - Review failed beers in {failed_file}")
        print(f"   - You can retry failed beers by running again with --resume")


if __name__ == "__main__":
    main()
