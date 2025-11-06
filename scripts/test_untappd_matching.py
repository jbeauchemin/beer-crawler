"""
Script de test pour valider la logique de matching Untappd
"""

from untappd_enrichment import UntappdEnricher


def test_matching():
    """Teste la logique de matching avec des exemples réels"""

    enricher = UntappdEnricher()

    # Exemple de bière de votre JSON
    beer = {
        "name": "Fardeau",
        "producer": "Messorem Bracitorium",
        "volume": "473ml"
    }

    # Résultats simulés de l'API Untappd
    api_results = [
        {
            "bid": "123456",
            "beer_name": "Fardeau",
            "brewery_name": "Brasserie Messorem Bracitorium",
            "beer_style": "IPA",
            "beer_abv": 6.2,
            "rating_score": 3.85,
            "rating_count": 250
        },
        {
            "bid": "789012",
            "beer_name": "Fardeau Xtrm Turbo",
            "brewery_name": "Brasserie Messorem Bracitorium",
            "beer_style": "Double IPA",
            "beer_abv": 8.5,
            "rating_score": 3.92,
            "rating_count": 180
        },
        {
            "bid": "345678",
            "beer_name": "Fardeau",
            "brewery_name": "Different Brewery",  # Mauvais producteur
            "beer_style": "Pale Ale",
            "beer_abv": 5.0,
            "rating_score": 3.50,
            "rating_count": 50
        }
    ]

    print("="*60)
    print("🧪 TEST DE MATCHING UNTAPPD")
    print("="*60)
    print(f"\nBière recherchée:")
    print(f"  Nom:        {beer['name']}")
    print(f"  Producteur: {beer['producer']}")
    print(f"  Volume:     {beer['volume']}")

    print(f"\n{'='*60}")
    print("Résultats de l'API:\n")

    for i, api_result in enumerate(api_results, 1):
        print(f"\n{i}. {api_result['beer_name']}")
        print(f"   Brasserie:  {api_result['brewery_name']}")
        print(f"   Style:      {api_result['beer_style']}")
        print(f"   ABV:        {api_result['beer_abv']}%")
        print(f"   Rating:     {api_result['rating_score']} ({api_result['rating_count']} ratings)")

        # Teste le matching
        is_match = enricher.is_exact_match(beer, api_result)

        print(f"   Match:      {'✅ OUI' if is_match else '❌ NON'}")

        # Affiche les détails de la comparaison
        print(f"\n   Détails de comparaison:")
        name_overlap = enricher.token_overlap_ratio(beer['name'], api_result['beer_name'])
        print(f"   - Overlap nom:       {name_overlap*100:.0f}%")

        producer_overlap = enricher.token_overlap_ratio(beer['producer'], api_result['brewery_name'])
        print(f"   - Overlap producteur: {producer_overlap*100:.0f}%")

    print(f"\n{'='*60}")
    print("✅ Test terminé!")
    print("="*60)


def test_multiple_cases():
    """Teste plusieurs cas de matching"""

    enricher = UntappdEnricher()

    test_cases = [
        {
            "description": "Match exact - nom et producteur identiques",
            "beer": {"name": "Fardeau", "producer": "Messorem Bracitorium"},
            "api": {"beer_name": "Fardeau", "brewery_name": "Brasserie Messorem Bracitorium"},
            "expected": True
        },
        {
            "description": "Pas de match - variante avec mots supplémentaires",
            "beer": {"name": "Fardeau", "producer": "Messorem Bracitorium"},
            "api": {"beer_name": "Fardeau Xtrm Turbo", "brewery_name": "Brasserie Messorem Bracitorium"},
            "expected": False
        },
        {
            "description": "Match avec accents et casse différents",
            "beer": {"name": "La Saison du Tracteur", "producer": "Trou du Diable"},
            "api": {"beer_name": "La Saison Du Tracteur", "brewery_name": "Le Trou du Diable"},
            "expected": True
        },
        {
            "description": "Pas de match - producteur différent",
            "beer": {"name": "Pale Ale", "producer": "Brasserie A"},
            "api": {"beer_name": "Pale Ale", "brewery_name": "Brasserie B"},
            "expected": False
        },
        {
            "description": "Match avec mots de brasserie",
            "beer": {"name": "Camerise", "producer": "Menaud"},
            "api": {"beer_name": "Camerise", "brewery_name": "Microbrasserie Menaud"},
            "expected": True
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
        print(f"   API:   {test['api']['beer_name']} - {test['api']['brewery_name']}")

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
    print("\n🍺 TEST DE LA LOGIQUE DE MATCHING UNTAPPD\n")

    # Test avec exemples
    test_matching()

    # Tests de cas multiples
    test_multiple_cases()
