#!/usr/bin/env python3
"""
Script to classify beers using local LLM (Ollama with Mixtral).

Generates:
- style_code: One of 10 predefined beer styles
- flavors: 2-3 flavor profiles from 10 options (min 1, max 4)
- bitterness_level: LOW/MEDIUM/HIGH based on IBU
- alcohol_strength: ALCOHOL_FREE/LIGHT/MEDIUM/STRONG based on ABV
- description_fr: Fun, friendly, casual French description (2-3 sentences)
- description_en: Fun, friendly, casual English description (2-3 sentences)

Note: Descriptions are written in an exciting, approachable tone - like recommending
beer to a friend at a bar, not formal beer reviews!
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
import requests
from tqdm import tqdm


# Beer classification schema
STYLE_CODES = [
    'BLONDE_GOLDEN',    # Blonde / Golden Ale
    'WHEAT_WITBIER',    # Wheat Beer / Witbier
    'IPA',              # IPA
    'PALE_ALE',         # Pale Ale
    'RED_AMBER',        # Red Ale / Amber
    'LAGER_PILSNER',    # Lager / Pilsner
    'SAISON_FARMHOUSE', # Saison / Farmhouse Ale
    'SOUR_TART',        # Sour / Tart Beer
    'STOUT_PORTER',     # Stout / Porter
    'CIDER',            # Cider
]

FLAVOR_CODES = [
    'HOPPY_BITTER',           # Hoppy / Bitter
    'CITRUS_TROPICAL',        # Citrus / Tropical
    'MALTY_GRAINY',           # Malty / Grainy
    'CARAMEL_TOFFEE_SWEET',   # Caramel / Toffee / Sweet
    'CHOCOLATE_COFFEE',       # Chocolate / Coffee
    'RED_FRUITS_BERRIES',     # Red Fruits / Berries
    'ORCHARD_FRUITS',         # Peach, Pear & Orchard Fruits
    'SPICY_HERBAL',           # Spicy / Herbal
    'WOODY_SMOKY',            # Woody / Smoky
    'SOUR_TART_FUNKY',        # Sour / Tart / Funky
]

BITTERNESS_LEVELS = ['LOW', 'MEDIUM', 'HIGH']
ALCOHOL_STRENGTHS = ['ALCOHOL_FREE', 'LIGHT', 'MEDIUM', 'STRONG']


def build_classification_prompt(beer: Dict) -> str:
    """Build the prompt for LLM classification."""

    # Extract key info
    name = beer.get('name', 'Unknown')
    producer = beer.get('producer', 'Unknown')
    abv = beer.get('abv_normalized')
    ibu = beer.get('ibu_normalized')

    # Combine all descriptions
    descriptions = beer.get('descriptions', {})
    desc_text = "\n".join([f"- {source}: {desc}" for source, desc in descriptions.items()])

    # Combine all styles mentioned
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
   - LIGHT: 0.5-5%
   - MEDIUM: 5-7%
   - STRONG: 7-15%

5. description_fr - Write a FUN, FRIENDLY French description (2-3 sentences, 50-80 words)
   Make it friendly, funny, and pleasant to read. Use a casual tone like talking to a friend.

6. description_en - Write a FUN, FRIENDLY English description (2-3 sentences, 50-80 words)
   Same: make it casual, fun, and enjoyable to read. Don't be too serious. Think beer blog vibes.

CRITICAL RULES:
- Use ONLY the exact codes provided
- MUST have 2-3 flavors (rarely 1, occasionally 4)
- Descriptions MUST be fun, casual, exciting - NO formal beer-review language!
- Write like you're talking to a friend, not writing a wine review!

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
                'format': 'json',  # Request JSON output
            },
            timeout=120  # 2 minutes timeout for Mixtral
        )

        if response.status_code != 200:
            print(f"❌ Ollama API error: {response.status_code}")
            return None

        result = response.json()
        response_text = result.get('response', '').strip()

        # Parse the JSON response
        try:
            classification = json.loads(response_text)
            return classification
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse LLM response as JSON: {e}")
            print(f"Response was: {response_text[:200]}...")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        return None


def validate_classification(classification: Dict) -> bool:
    """Validate that classification follows the rules."""

    if not classification:
        return False

    # Check required fields
    required_fields = ['style_code', 'flavors', 'bitterness_level', 'alcohol_strength',
                      'description_fr', 'description_en']
    if not all(field in classification for field in required_fields):
        print(f"❌ Missing required fields")
        return False

    # Validate style_code
    if classification['style_code'] not in STYLE_CODES:
        print(f"❌ Invalid style_code: {classification['style_code']}")
        return False

    # Validate flavors
    flavors = classification['flavors']
    if not isinstance(flavors, list) or len(flavors) < 1 or len(flavors) > 4:
        print(f"❌ Invalid flavors count: {len(flavors)}")
        return False

    # Warn if only 1 flavor (should be rare)
    if len(flavors) == 1:
        print(f"⚠️  Warning: Only 1 flavor for {classification.get('style_code', 'unknown')} beer - consider if more apply")

    if not all(f in FLAVOR_CODES for f in flavors):
        invalid = [f for f in flavors if f not in FLAVOR_CODES]
        print(f"❌ Invalid flavor codes: {invalid}")
        return False

    # Validate bitterness_level
    if classification['bitterness_level'] not in BITTERNESS_LEVELS:
        print(f"❌ Invalid bitterness_level: {classification['bitterness_level']}")
        return False

    # Validate alcohol_strength
    if classification['alcohol_strength'] not in ALCOHOL_STRENGTHS:
        print(f"❌ Invalid alcohol_strength: {classification['alcohol_strength']}")
        return False

    return True


def classify_beer(beer: Dict, model: str = "mixtral:latest") -> Optional[Dict]:
    """Classify a single beer using LLM."""

    prompt = build_classification_prompt(beer)
    classification = call_ollama(prompt, model)

    if classification and validate_classification(classification):
        return classification

    return None


def main():
    if len(sys.argv) < 3:
        print("Usage: python classify_beers_llm.py <input.json> <output.json> [--model MODEL] [--limit N]")
        print("\nOptions:")
        print("  --model MODEL    Ollama model to use (default: mixtral:latest)")
        print("  --limit N        Only process first N beers (for testing)")
        print("\nExample:")
        print("  python classify_beers_llm.py beers_cleaned.json beers_classified.json")
        print("  python classify_beers_llm.py beers_cleaned.json test_output.json --limit 10")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    # Parse optional arguments
    model = "mixtral:latest"
    limit = None

    for i, arg in enumerate(sys.argv):
        if arg == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]
        elif arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    if not input_file.exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)

    print(f"🍺 Beer Classification with LLM")
    print(f"📖 Input: {input_file}")
    print(f"💾 Output: {output_file}")
    print(f"🤖 Model: {model}")
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

    # Check if Ollama is running
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code != 200:
            print("❌ Error: Ollama is not responding. Make sure 'ollama serve' is running.")
            sys.exit(1)
    except requests.exceptions.RequestException:
        print("❌ Error: Cannot connect to Ollama. Make sure 'ollama serve' is running.")
        sys.exit(1)

    # Process beers
    classified_beers = []
    failed_beers = []

    print(f"🚀 Starting classification with {model}...")
    print()

    for i, beer in enumerate(tqdm(beers, desc="Classifying beers")):
        classification = classify_beer(beer, model)

        if classification:
            # Merge classification with original beer data
            classified_beer = {**beer, **classification}
            classified_beers.append(classified_beer)
        else:
            failed_beers.append({
                'name': beer.get('name'),
                'producer': beer.get('producer'),
                'reason': 'Classification failed or invalid'
            })
            # Still add the beer but without classification
            classified_beers.append(beer)

        # Save progress every 50 beers
        if (i + 1) % 50 == 0:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(classified_beers, f, ensure_ascii=False, indent=2)

    # Final save
    print()
    print(f"💾 Saving final results to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(classified_beers, f, ensure_ascii=False, indent=2)

    # Save failed beers if any
    if failed_beers:
        failed_file = output_file.parent / f"{output_file.stem}_failed.json"
        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump(failed_beers, f, ensure_ascii=False, indent=2)
        print(f"⚠️  Failed beers saved to: {failed_file}")

    # Summary
    print()
    print(f"✅ Classification complete!")
    print(f"   Total beers: {len(beers)}")
    print(f"   Successfully classified: {len(beers) - len(failed_beers)}")
    print(f"   Failed: {len(failed_beers)}")
    print()
    print(f"📄 Output saved to: {output_file}")


if __name__ == "__main__":
    main()
