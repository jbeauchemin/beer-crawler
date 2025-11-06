"""
Script de test pour valider la logique de matching UPC
"""

import json
from upc_enrichment import UPCEnricher


def test_matching():
    """Teste la logique de matching avec des exemples réels"""

    enricher = UPCEnricher()

    # Exemple de bière de votre JSON
    beer = {
        "name": "Fardeau",
        "producer": "Messorem Bracitorium",
        "volume": "473ml"
    }

    # Résultats de l'API (tirés de votre exemple)
    api_results = [
        {
            "Maker": "Brasserie Messorem Bracitorium inc.",
            "product": "Fardeau",
            "volume": "473 ml",
            "upc": "877951002328"
        },
        {
            "Maker": "Brasserie Messorem Bracitorium inc.",
            "product": "Fardeau Xtrm Turbo",
            "volume": "473 ml",
            "upc": "877951002304"
        }
    ]

    print("="*60)
    print("🧪 TEST DE MATCHING UPC")
    print("="*60)
    print(f"\nBière recherchée:")
    print(f"  Nom:        {beer['name']}")
    print(f"  Producteur: {beer['producer']}")
    print(f"  Volume:     {beer['volume']}")

    print(f"\n{'='*60}")
    print("Résultats de l'API:\n")

    for i, api_result in enumerate(api_results, 1):
        print(f"\n{i}. {api_result['product']}")
        print(f"   Maker:  {api_result['Maker']}")
        print(f"   Volume: {api_result['volume']}")
        print(f"   UPC:    {api_result['upc']}")

        # Teste le matching
        is_match = enricher.is_exact_match(beer, api_result)

        print(f"   Match:  {'✅ OUI' if is_match else '❌ NON'}")

        # Affiche les détails de la comparaison
        print(f"\n   Détails de comparaison:")
        beer_name_norm = enricher.normalize_text(beer['name'])
        api_product_norm = enricher.normalize_text(api_result['product'])
        print(f"   - Nom bière normalisé:  '{beer_name_norm}'")
        print(f"   - Nom API normalisé:    '{api_product_norm}'")
        print(f"   - Noms identiques:      {beer_name_norm == api_product_norm}")

        beer_producer_norm = enricher.normalize_text(beer['producer'])
        api_maker_norm = enricher.normalize_text(api_result['Maker'])
        print(f"   - Producteur normalisé: '{beer_producer_norm}'")
        print(f"   - Maker normalisé:      '{api_maker_norm}'")

        beer_volume_norm = enricher.normalize_volume(beer['volume'])
        api_volume_norm = enricher.normalize_volume(api_result['volume'])
        print(f"   - Volume bière:         '{beer_volume_norm}'")
        print(f"   - Volume API:           '{api_volume_norm}'")

    print(f"\n{'='*60}")
    print("✅ Test terminé!")
    print("="*60)


def test_multiple_cases():
    """Teste plusieurs cas de matching"""

    enricher = UPCEnricher()

    test_cases = [
        {
            "description": "Match exact - même nom",
            "beer": {"name": "Fardeau", "producer": "Messorem", "volume": "473ml"},
            "api": {"Maker": "Messorem", "product": "Fardeau", "volume": "473 ml"},
            "expected": True
        },
        {
            "description": "Pas de match - variante avec mots supplémentaires",
            "beer": {"name": "Fardeau", "producer": "Messorem", "volume": "473ml"},
            "api": {"Maker": "Messorem", "product": "Fardeau Xtrm Turbo", "volume": "473 ml"},
            "expected": False
        },
        {
            "description": "Match avec différences de casse et ponctuation",
            "beer": {"name": "La Belle IPA", "producer": "Brasserie XYZ", "volume": "355ml"},
            "api": {"Maker": "Brasserie XYZ Inc.", "product": "La Belle IPA", "volume": "355 ml"},
            "expected": True
        },
        {
            "description": "Pas de match - producteur différent",
            "beer": {"name": "Pale Ale", "producer": "Brasserie A", "volume": "473ml"},
            "api": {"Maker": "Brasserie B", "product": "Pale Ale", "volume": "473 ml"},
            "expected": False
        },
        {
            "description": "Match avec nom composé",
            "beer": {"name": "Saison du Tracteur", "producer": "Trou du Diable", "volume": "341ml"},
            "api": {"Maker": "Brasserie Trou du Diable", "product": "Saison du Tracteur", "volume": "341 ml"},
            "expected": True
        },
        {
            "description": "Match avec style ajouté par l'API (1 mot)",
            "beer": {"name": "Blanche de Fox", "producer": "Frontibus", "volume": "473ml"},
            "api": {"Maker": "Microbrasserie au Frontibus", "product": "Blanche de Fox Blanche", "volume": "473 ml"},
            "expected": True
        },
        {
            "description": "Match avec style ajouté par l'API (1 mot)",
            "beer": {"name": "Pop Gose the World", "producer": "Hopfenstark", "volume": "473ml"},
            "api": {"Maker": "Brasserie Hopfenstark", "product": "Pop gose the world Gose", "volume": "473 ml"},
            "expected": True
        },
        {
            "description": "Pas de match - variante avec 2+ mots supplémentaires",
            "beer": {"name": "Fardeau", "producer": "Messorem", "volume": "473ml"},
            "api": {"Maker": "Messorem Bracitorium", "product": "Fardeau Xtrm Turbo", "volume": "473 ml"},
            "expected": False
        }
    ]

    print("\n" + "="*60)
    print("🧪 TESTS DE CAS MULTIPLES")
    print("="*60)

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['description']}")
        print(f"   Bière: {test['beer']['name']} - {test['beer']['producer']}")
        print(f"   API:   {test['api']['product']} - {test['api']['Maker']}")

        result = enricher.is_exact_match(test['beer'], test['api'])
        expected = test['expected']

        if result == expected:
            print(f"   ✅ PASS (résultat: {result})")
            passed += 1
        else:
            print(f"   ❌ FAIL (attendu: {expected}, obtenu: {result})")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Résultats: {passed} tests réussis, {failed} tests échoués")
    print("="*60)


if __name__ == "__main__":
    print("\n🍺 TEST DE LA LOGIQUE DE MATCHING UPC\n")

    # Test avec votre exemple exact
    test_matching()

    # Tests de cas multiples
    test_multiple_cases()
