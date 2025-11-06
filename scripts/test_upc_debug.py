"""
Test de debug pour le cas Blanche de Fox
"""

from upc_enrichment import UPCEnricher


def test_blanche_fox():
    enricher = UPCEnricher()

    beer = {
        "name": "Blanche de Fox",
        "producer": "Frontibus"
    }

    api_results = [
        {
            "Maker": "Microbrasserie au Frontibus",
            "product": "BLANCHE DE FOX : BLANCHE",
            "volume": "473 ml",
            "upc": "123456"
        },
        {
            "Maker": "Microbrasserie au Frontibus",
            "product": "Blanche de Fox",
            "volume": "473 ml",
            "upc": "789012"
        }
    ]

    print("="*60)
    print("🐛 DEBUG: Blanche de Fox")
    print("="*60)

    print(f"\nBière:")
    print(f"  name: {beer['name']}")
    print(f"  producer: {beer['producer']}")

    print(f"\n{'='*60}")
    print("Test de matching:\n")

    for i, api_result in enumerate(api_results, 1):
        print(f"\n{i}. API Result:")
        print(f"   Maker: {api_result['Maker']}")
        print(f"   product: {api_result['product']}")

        # Normalize
        beer_producer_norm = enricher.normalize_text(beer['producer'])
        api_maker_norm = enricher.normalize_text(api_result['Maker'])
        beer_name_norm = enricher.normalize_text(beer['name'])
        api_product_norm = enricher.normalize_text(api_result['product'])

        print(f"\n   Normalisations:")
        print(f"   Beer producer: '{beer['producer']}' → '{beer_producer_norm}'")
        print(f"   API Maker:     '{api_result['Maker']}' → '{api_maker_norm}'")
        print(f"   Beer name:     '{beer['name']}' → '{beer_name_norm}'")
        print(f"   API product:   '{api_result['product']}' → '{api_product_norm}'")

        # Producer matching
        producer_words = set(beer_producer_norm.split())
        maker_words = set(api_maker_norm.split())
        print(f"\n   Producer words: {producer_words}")
        print(f"   Maker words:    {maker_words}")

        overlap = len(producer_words & maker_words)
        min_words = min(len(producer_words), len(maker_words))
        threshold = min_words * 0.7

        print(f"   Overlap: {overlap}")
        print(f"   Min words: {min_words}")
        print(f"   Threshold (70%): {threshold}")
        print(f"   Producer match: {overlap >= threshold}")

        # Name matching
        beer_words = beer_name_norm.split()
        api_words = api_product_norm.split()

        print(f"\n   Name words (beer): {beer_words}")
        print(f"   Name words (API):  {api_words}")
        print(f"   Lengths: {len(beer_words)} vs {len(api_words)}")

        if len(api_words) > len(beer_words):
            print(f"   API has more words - checking...")
            print(f"   Starts with beer name? {api_product_norm.startswith(beer_name_norm)}")
            extra_words = set(api_words) - set(beer_words)
            print(f"   Extra words: {extra_words}")

        # Name exact match
        names_match = beer_name_norm == api_product_norm
        print(f"   Names exactly match: {names_match}")

        # Full match test
        is_match = enricher.is_exact_match(beer, api_result)
        print(f"\n   ✅ FINAL MATCH: {is_match}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    test_blanche_fox()
