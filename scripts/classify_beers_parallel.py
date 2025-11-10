#!/usr/bin/env python3
"""
Parallel beer classification with OpenRouter API and Prisma-ready output.

Uses OpenRouter.ai to access multiple LLM providers (OpenAI, Anthropic, etc.)
for high-quality, reliable beer classification with retry logic.

Output Format: Prisma-ready JSON with the following structure:
{
  "codeBar": "...",
  "productName": "...",
  "abv": "6.50",
  "ibu": "45.00",
  "rating": "4.2",
  "numRatings": 1234,
  "alcoholStrength": "MEDIUM",  // Calculated from ABV in Python (100% accurate)
  "bitternessLevel": "HIGH",    // Calculated from IBU or inferred from style
  "descriptionFr": "...",
  "descriptionEn": "...",
  "style": {"code": "IPA", "name": "IPA"},
  "flavors": [{"code": "HOPPY_BITTER", "name": "Hoppy / Bitter"}, ...],
  "producer": {"name": "..."},
  "rawData": {...}  // All original beer data
}

Features:
- OpenRouter API for reliable, high-quality LLM access
- Parallel processing with configurable workers (2-3 recommended)
- Retry failed classifications up to 5 times (greatly reduced failure rate)
- Smart bitterness inference from beer style when IBU is missing
- Progress tracking (resume from where you left off with --resume)
- Saves after EVERY beer (can interrupt with Ctrl+C safely)
- Thread-safe incremental saving
- alcoholStrength & bitternessLevel calculated in Python (not LLM) for 100% accuracy
- Graceful shutdown on Ctrl+C

Recommended models:
- openai/gpt-4o-mini: Best value (~$0.20/1000 beers) ⭐
- openai/gpt-4o: Best quality (~$2.50/1000 beers)
- anthropic/claude-3.5-sonnet: Most creative (~$3.75/1000 beers)

Setup:
    1. Install dependencies: pip install openai
    2. Get API key: https://openrouter.ai/keys
    3. Set environment variable: export OPENROUTER_API_KEY=your_key_here

Usage:
    # First run with GPT-4o mini (recommended)
    export OPENROUTER_API_KEY=your_key_here
    python classify_beers_parallel.py input.json output.json --workers 2

    # Use GPT-4o for best quality
    python classify_beers_parallel.py input.json output.json --model openai/gpt-4o --workers 2

    # Resume after interruption (Ctrl+C or crash)
    python classify_beers_parallel.py input.json output.json --workers 2 --resume
"""

import json
import sys
import time
import threading
import signal
import os
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

try:
    from openai import OpenAI
except ImportError:
    print("❌ Error: openai package not installed")
    print("Please run: pip install openai")
    sys.exit(1)


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
    if beer.get('abv_normalized') is not None:
        try:
            return float(beer['abv_normalized'])
        except (TypeError, ValueError):
            pass

    # Try 'alcohol' field (e.g., "9.8%" or "6.5%")
    if 'alcohol' in beer:
        alcohol = beer['alcohol']
        if isinstance(alcohol, str):
            match = re.search(r'(\d+\.?\d*)\s*%', alcohol)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass

    return None


def calculate_alcohol_strength(abv: Optional[float]) -> str:
    """Calculate alcohol strength based on ABV thresholds.

    This is done in Python instead of by the LLM for 100% accuracy.

    Thresholds:
    - ALCOHOL_FREE: 0-0.5%
    - LIGHT: 0.5-5.0%
    - MEDIUM: 5.0-7.0%
    - STRONG: >7.0%
    """
    if abv is None:
        return "MEDIUM"  # Default for unknown ABV

    if abv < 0.5:
        return "ALCOHOL_FREE"
    elif abv < 5.0:
        return "LIGHT"
    elif abv < 7.0:
        return "MEDIUM"
    else:
        return "STRONG"


def calculate_bitterness_level(ibu: Optional[float]) -> str:
    """Calculate bitterness level based on IBU thresholds.

    This is done in Python instead of by the LLM for 100% accuracy.

    Thresholds:
    - LOW: 0-20 IBU
    - MEDIUM: 20-40 IBU
    - HIGH: 40+ IBU
    """
    if ibu is None:
        return "MEDIUM"  # Default for unknown IBU

    try:
        ibu_val = float(ibu)
    except (TypeError, ValueError):
        return "MEDIUM"

    if ibu_val < 20:
        return "LOW"
    elif ibu_val < 40:
        return "MEDIUM"
    else:
        return "HIGH"


def build_classification_prompt(beer: Dict) -> str:
    """Build the prompt for LLM classification (style, flavors, bitterness, descriptions)."""
    import json as _json

    name = beer.get('name', 'Unknown')
    producer = beer.get('producer', 'Unknown')
    abv = extract_abv(beer)
    ibu = beer.get('ibu_normalized') or beer.get('untappd_ibu')

    raw_json = _json.dumps(beer, ensure_ascii=False, indent=2)

    prompt = f"""You are a BEER CLASSIFICATION ENGINE.

Your job:
- Read the raw beer data.
- Infer the best style_code, flavor codes, and bitterness_level.
- Write fun, friendly descriptions in French and English.
- Follow ALL rules strictly.

====================
RAW BEER DATA
====================
Name: {name}
Producer: {producer}
ABV: {abv if abv is not None else "Unknown"} % (alcohol by volume)
IBU: {ibu if ibu is not None else "Unknown"}

Full JSON:
{raw_json}

====================
STYLE CODE
====================

You MUST choose EXACTLY ONE style_code from:

- BLONDE_GOLDEN      (Blonde / Golden Ale)
- WHEAT_WITBIER      (Wheat Beer / Witbier)
- IPA                (IPA, NEIPA, DIPA, TIPA, Double IPA, Triple IPA)
- PALE_ALE           (Pale Ale)
- RED_AMBER          (Red Ale / Amber)
- LAGER_PILSNER      (Lager / Pilsner)
- SAISON_FARMHOUSE   (Saison / Farmhouse Ale, Grisette)
- SOUR_TART          (Sour / Tart Beer, Smoothie Sour, Fruited Sour, “Sûre”)
- STOUT_PORTER       (Stout / Porter)
- CIDER              (Cider / Cidre)

Mapping rules (examples):
- Any IPA / NEIPA / Double / Triple IPA / TIPA keyword → IPA
- “Smoothie”, “Smoothie Sour”, “Fruited Sour”, “Sûre”, “Sure”, “Gose” → SOUR_TART
- Any style string that contains "Sour -" (for example Untappd styles like "Sour - Other",
  "Sour - Fruited Gose", etc.) should ALMOST ALWAYS be mapped to SOUR_TART,
  even if another source says "Blanche", "Wheat", or something similar.
- “Blonde”, “Golden” → BLONDE_GOLDEN
- “Blanche”, “Witbier”, “Wheat” → WHEAT_WITBIER
- “Cream Ale” → BLONDE_GOLDEN (unless clearly described as a wheat / witbier)
- “Red Ale”, “Amber” → RED_AMBER
- “Lager”, “Pilsner”, “Pils” → LAGER_PILSNER
- “Saison”, “Farmhouse”, “Grisette” → SAISON_FARMHOUSE
- “Stout”, “Porter” → STOUT_PORTER
- “Cidre”, “Cider” → CIDER

If unsure, pick the MOST plausible style based on the data. NEVER return null.

====================
FLAVORS
====================

You MUST choose between 2 and 4 flavor codes that best represent the beer.

Allowed flavor codes:

- HOPPY_BITTER          (Hoppy / Bitter)
- CITRUS_TROPICAL       (Citrus / Tropical)
- MALTY_GRAINY          (Malty / Grainy)
- CARAMEL_TOFFEE_SWEET  (Caramel / Toffee / Sweet)
- CHOCOLATE_COFFEE      (Chocolate / Coffee)
- RED_FRUITS_BERRIES    (Red Fruits / Berries)
- ORCHARD_FRUITS        (Peach, Pear & Orchard Fruits)
- SPICY_HERBAL          (Spicy / Herbal)
- WOODY_SMOKY           (Woody / Smoky)
- SOUR_TART_FUNKY       (Sour / Tart / Funky)

Guidelines:
- IPA / NEIPA / tropical hops (Citra, Galaxy, Nelson, etc.) → HOPPY_BITTER + CITRUS_TROPICAL
- Mango, passion fruit, guava, smoothie, tropical juice → CITRUS_TROPICAL
- Vanilla, dessert-like, pastry, sweet finish → CARAMEL_TOFFEE_SWEET
- Chocolate, coffee, espresso, roast → CHOCOLATE_COFFEE
- Raspberry, cherry, berries → RED_FRUITS_BERRIES
- Peach, pear, apricot → ORCHARD_FRUITS
- Spices, pepper, coriander, herbs → SPICY_HERBAL
- Oak, smoke, barrel → WOODY_SMOKY
- Sour, tart, funky, wild, yogurt-like, Gose → SOUR_TART_FUNKY

Return an array of 2–4 codes, no more, no less. NEVER empty, NEVER null.

====================
BITTERNESS LEVEL
====================

Field: bitterness_level

Allowed values:
- LOW
- MEDIUM
- HIGH

If IBU is known:
- 0 <= IBU < 20   → LOW
- 20 <= IBU <= 40 → MEDIUM
- IBU > 40        → HIGH

If IBU is UNKNOWN:
- If style_code in ["SOUR_TART", "BLONDE_GOLDEN", "WHEAT_WITBIER", "CIDER"] → LOW
- If style_code in ["LAGER_PILSNER", "SAISON_FARMHOUSE", "RED_AMBER"] → MEDIUM
- If style_code in ["IPA", "PALE_ALE", "STOUT_PORTER"] → MEDIUM by default
- Only choose HIGH if the description clearly suggests STRONG bitterness:
  - e.g. very bitter, resinous, biting, aggressive hops, sharp bitterness.

Never return null for bitterness_level.

Note: The final database may recompute bitterness later. Still, you MUST provide your best guess here.

====================
DESCRIPTIONS
====================

You MUST return:

- description_fr:
  - Langue: français
  - Ton: fun, convivial, comme si tu parlais à un·e client·e dans un bar ou une boutique.
  - Tu peux t’adresser directement à la personne (“tu”, “vous”) et utiliser des formules comme
    “Parfaite si tu aimes…”, “Idéale pour ceux qui apprécient…”.
  - Longueur: 2–3 phrases, environ 50–90 mots.
  - Mentionne les arômes, saveurs, texture, style, ambiance générale.
  - Interdictions:
    - Ne jamais mentionner ou suggérer la surconsommation: pas de “sans modération”,
      “encore une dernière”, “impossible de s’arrêter”, etc.
    - Ne pas présenter la bière comme solution aux problèmes ou au stress
      (pas de “pour oublier ta journée”, “pour décompresser de la semaine”, etc.).
    - Ne jamais mentionner ou cibler des mineurs (pas de “jeunes”, “ados”, etc.).

- description_en:
  - Language: English
  - Tone: friendly, conversational, like a beer shop talking to a customer.
  - You MAY address the reader directly (“you”) with phrases like
    “Great if you enjoy…”, “Perfect for anyone who loves…”.
  - Length: 2–3 sentences, about 50–90 words.
  - Mention aromas, flavors, mouthfeel, style, overall vibe.
  - Forbidden:
    - No encouragement of overconsumption: no “drink without moderation”,
      “one more won’t hurt”, “impossible to stop”, etc.
    - Do not frame the beer as a way to cope with stress or problems
      (“to forget your day”, “to handle stress”, etc.).
    - Never mention or target minors (“kids”, “teens”, “youngsters”, etc.).

- In BOTH languages, do NOT describe specific situations or moments of consumption such as
  “après une longue journée”, “soirée entre amis”, “journée ensoleillée”,
  “moment de fraîcheur”, “moment de détente”, “pour accompagner un repas”,
  “after a long day”, “sunny day”, “evening with friends”, “for a relaxed moment”,
  “to unwind”, “to share with friends”, etc.
  Focus ONLY on flavors, aromas, texture, appearance and the character of the beer itself.

Both descriptions are REQUIRED. Never return null or empty strings.

Vary your openings and wording. Do NOT start every description with the same phrase.

====================
CRITICAL CONSTRAINTS
====================

1. style_code MUST be one of:
   {", ".join(STYLE_CODES)}

2. flavors MUST be an array of 2 to 4 codes from:
   {", ".join(FLAVOR_CODES)}

3. bitterness_level MUST be one of:
   LOW, MEDIUM, HIGH

4. NEVER return null for:
   - style_code
   - flavors
   - bitterness_level
   - description_fr
   - description_en

====================
OUTPUT FORMAT
====================

Respond with ONLY valid JSON, no comments, no extra text:

{{
  "style_code": "IPA",
  "flavors": ["HOPPY_BITTER", "CITRUS_TROPICAL"],
  "bitterness_level": "HIGH",
  "description_fr": " ... ",
  "description_en": " ... "
}}

Now classify the beer and generate the JSON.
"""

    return prompt
def call_openrouter(prompt: str, model: str = "openai/gpt-4o-mini",
                    temperature: float = 0.8, api_key: str = None) -> Optional[Dict]:
    """Call OpenRouter API to get classification."""
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY")
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            response_format={"type": "json_object"}
        )

        response_text = response.choices[0].message.content.strip()

        try:
            classification = json.loads(response_text)
            return classification
        except json.JSONDecodeError:
            return None

    except Exception as e:
        print(f"  ❌ API error: {e}")
        return None


def validate_classification(classification: Dict) -> bool:
    """Validate that classification follows the rules."""
    if not classification:
        return False

    required_fields = ['style_code', 'flavors', 'bitterness_level',
                       'description_fr', 'description_en']
    if not all(field in classification for field in required_fields):
        return False

    if classification['style_code'] not in STYLE_CODES:
        return False

    flavors = classification['flavors']
    # MINIMUM 2 flavors, MAXIMUM 4
    if not isinstance(flavors, list) or len(flavors) < 2 or len(flavors) > 4:
        return False

    if not all(f in FLAVOR_CODES for f in flavors):
        return False

    if classification['bitterness_level'] not in BITTERNESS_LEVELS:
        return False

    return True


def infer_bitterness_from_style(style_code: str) -> str:
    """Infer typical bitterness level from beer style when IBU is not available."""
    style_to_bitterness = {
        'IPA': 'MEDIUM',           # IPAs sans IBU → MEDIUM par défaut
        'PALE_ALE': 'MEDIUM',
        'STOUT_PORTER': 'MEDIUM',
        'BLONDE_GOLDEN': 'LOW',
        'WHEAT_WITBIER': 'LOW',
        'SOUR_TART': 'LOW',
        'CIDER': 'LOW',
        'LAGER_PILSNER': 'MEDIUM',
        'SAISON_FARMHOUSE': 'MEDIUM',
        'RED_AMBER': 'MEDIUM',
    }
    return style_to_bitterness.get(style_code, 'MEDIUM')


def classify_beer_with_retry(beer: Dict, model: str = "openai/gpt-4o-mini",
                             api_key: str = None, max_retries: int = 5) -> Optional[Dict]:
    """Call LLM to classify beer (style, flavors, descriptions only)."""
    for attempt in range(max_retries):
        prompt = build_classification_prompt(beer)
        classification = call_openrouter(prompt, model, api_key=api_key)

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
    """Format beer data for Prisma schema.

    This function does ALL Python calculations:
    - alcoholStrength: Calculated from ABV (100% accurate)
    - bitternessLevel: Calculated from IBU, or inferred from style if IBU missing
    - All other fields: Formatted for Prisma schema
    """
    # Calculate alcoholStrength from ABV (Python calculation, not LLM)
    abv_value = extract_abv(beer)
    alcohol_strength = calculate_alcohol_strength(abv_value)

    # Calculate bitternessLevel: IBU first, then ABV+style, then style, then default
    ibu_value = beer.get('untappd_ibu') or beer.get('ibu_normalized')
    if ibu_value is not None:
        bitterness_level = calculate_bitterness_level(ibu_value)
    elif classification and 'style_code' in classification:
        style_code = classification['style_code']
        # Special rule: IPA costaud (ABV >= 7.5) → HIGH si pas d'IBU
        if style_code == "IPA" and abv_value is not None and abv_value >= 7.5:
            bitterness_level = "HIGH"
        else:
            bitterness_level = infer_bitterness_from_style(style_code)
    else:
        bitterness_level = "MEDIUM"

    # Get rating info
    num_ratings = beer.get('untappd_rating_count', 0)
    rating = beer.get('untappd_rating', 0)

    # Only include rating if there are actual ratings (numRatings > 0)
    rating_str = str(rating) if num_ratings and num_ratings > 0 else None

    prisma_beer = {
        "codeBar": beer.get('upc') or None,
        "productName": beer.get('name'),
        "abv": str(abv_value) if abv_value is not None else None,
        "ibu": str(ibu_value) if ibu_value is not None else None,
        "rating": rating_str,
        "numRatings": num_ratings or 0,
        "imageUrl": get_first_image(beer.get('photo_urls', {})),
        "producer": {
            "name": beer.get('producer')
        },
        "rawData": beer,
        # Always include these (calculated from actual data)
        "alcoholStrength": alcohol_strength,
        "bitternessLevel": bitterness_level,
        # Classification fields (null if LLM failed)
        "descriptionFr": classification['description_fr'] if classification else None,
        "descriptionEn": classification['description_en'] if classification else None,
        "style": {
            "code": classification['style_code'],
            "name": STYLE_NAMES[classification['style_code']]
        } if classification else None,
        "flavors": [
            {
                "code": flavor_code,
                "name": FLAVOR_NAMES[flavor_code]
            }
            for flavor_code in (classification['flavors'] if classification else [])
        ] if classification else None
    }

    return prisma_beer


class ThreadSafeProgress:
    """Thread-safe progress tracking."""
    def __init__(self):
        self.lock = threading.Lock()
        self.classified_beers: List[Dict] = []
        self.failed_beers: List[Dict] = []
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
    index, beer, model, api_key = args
    beer_name = beer.get('name', 'Unknown')

    # Classify with retry (5 attempts)
    classification = classify_beer_with_retry(beer, model, api_key=api_key, max_retries=5)

    # Format for Prisma (includes calculated alcohol_strength and bitterness_level)
    prisma_beer = format_for_prisma(beer, classification)

    return {
        'index': index,
        'beer': prisma_beer,
        'classification': classification,
        'name': beer_name,
        'producer': beer.get('producer'),
        'upc': beer.get('upc')
    }


# Global variables for signal handler
_output_file: Optional[Path] = None
_progress: Optional[ThreadSafeProgress] = None


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully by saving progress before exiting."""
    print("\n\n⚠️  Interrupted by user (Ctrl+C)")
    if _output_file and _progress:
        print("💾 Saving progress before exiting...")
        try:
            with open(_output_file, 'w', encoding='utf-8') as f:
                json.dump(_progress.get_all_beers(), f, ensure_ascii=False, indent=2)
            stats = _progress.get_stats()
            print(f"✅ Saved {stats['classified']} classified beers to {_output_file}")
            print(f"💡 Use --resume to continue from where you left off")
        except Exception as e:
            print(f"❌ Error saving progress: {e}")
    print("👋 Exiting...")
    sys.exit(0)


def main():
    if len(sys.argv) < 3:
        print("Usage: python classify_beers_parallel.py <input.json> <output.json> [OPTIONS]")
        print("\nOptions:")
        print("  --model MODEL      OpenRouter model (default: openai/gpt-4o-mini)")
        print("                     Examples: openai/gpt-4o, anthropic/claude-3.5-sonnet")
        print("  --api-key KEY      OpenRouter API key (or set OPENROUTER_API_KEY env var)")
        print("  --workers N        Number of parallel workers (default: 2)")
        print("  --limit N          Only process first N beers (for testing)")
        print("  --resume           Resume from last checkpoint")
        print("\nRecommended models:")
        print("  openai/gpt-4o-mini          - Best value ($0.20/1000 beers) ⭐")
        print("  openai/gpt-4o               - Best quality ($2.50/1000 beers)")
        print("  anthropic/claude-3.5-sonnet - Most creative ($3.75/1000 beers)")
        print("\nExample:")
        print("  export OPENROUTER_API_KEY=your_key_here")
        print("  python classify_beers_parallel.py beers_cleaned.json beers_prisma.json --workers 2")
        print("  python classify_beers_parallel.py beers_cleaned.json beers_prisma.json --model openai/gpt-4o --workers 3")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    # Install signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Parse arguments
    model = "openai/gpt-4o-mini"
    api_key = None
    workers = 2
    limit = None
    resume = False

    for i, arg in enumerate(sys.argv):
        if arg == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]
        elif arg == "--api-key" and i + 1 < len(sys.argv):
            api_key = sys.argv[i + 1]
        elif arg == "--workers" and i + 1 < len(sys.argv):
            workers = int(sys.argv[i + 1])
        elif arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        elif arg == "--resume":
            resume = True

    # Check API key
    if not api_key:
        api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        print("❌ Error: OpenRouter API key not found")
        print("Please either:")
        print("  1. Set environment variable: export OPENROUTER_API_KEY=your_key_here")
        print("  2. Pass as argument: --api-key your_key_here")
        print("\nGet your API key at: https://openrouter.ai/keys")
        sys.exit(1)

    if not input_file.exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)

    print(f"🍺 Parallel Beer Classification with OpenRouter")
    print(f"📖 Input: {input_file}")
    print(f"💾 Output: {output_file}")
    print(f"🤖 Model: {model}")
    print(f"⚡ Workers: {workers}")
    print(f"🔄 Max retries: 5")
    print()

    # Load beers
    print(f"📖 Loading beers...")
    with open(input_file, 'r', encoding='utf-8') as f:
        beers = json.load(f)

    # Load already processed beers if resuming
    already_processed = set()
    if resume and output_file.exists():
        print(f"🔄 Resume mode: Loading already processed beers...")
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_beers = json.load(f)
            # Track which beers are already done by their name+producer combo
            for beer in existing_beers:
                raw_data = beer.get('rawData', {})
                beer_key = f"{raw_data.get('name', '')}|{raw_data.get('producer', '')}"
                already_processed.add(beer_key)
        print(f"✅ Found {len(already_processed)} already processed beers")

    # Filter out already processed beers
    if already_processed:
        original_count = len(beers)
        beers = [b for b in beers if f"{b.get('name', '')}|{b.get('producer', '')}" not in already_processed]
        skipped = original_count - len(beers)
        print(f"⏭️  Skipping {skipped} already processed beers")

    if limit:
        beers = beers[:limit]
        print(f"⚠️  Testing mode: Processing only {limit} beers")

    print(f"✅ Loaded {len(beers)} beers to process")
    print()

    # Thread-safe progress
    progress = ThreadSafeProgress()

    # Set global variables for signal handler
    global _output_file, _progress
    _output_file = output_file
    _progress = progress

    # Load existing beers into progress if resuming
    if resume and output_file.exists():
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_beers = json.load(f)
            for beer in existing_beers:
                progress.add_classified(beer)

    # Process beers in parallel
    print(f"🚀 Starting parallel classification with {workers} workers...")
    print(f"💡 Tip: Each worker processes beers independently for {workers}x speed")
    print(f"💾 Auto-save: Progress saved after EVERY beer")
    print(f"⚠️  Safe to interrupt: Press Ctrl+C anytime, use --resume to continue")
    print()

    # Prepare work items (include API key)
    work_items = [(i, beer, model, api_key) for i, beer in enumerate(beers)]

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

                # Save after EVERY beer (critical for resume capability)
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