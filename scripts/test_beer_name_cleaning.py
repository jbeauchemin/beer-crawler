"""
Script de test pour valider le nettoyage des noms de bières
"""

from clean_beer_names import BeerNameCleaner


def test_cleaning():
    """Teste le nettoyage avec des exemples réels"""

    cleaner = BeerNameCleaner(dry_run=True)

    # Exemples fournis par l'utilisateur
    test_beers = [
        {
            "name": "Messorem – Not so doomed après tout",
            "producer": "Messorem Bracitorium",
            "expected": "Not so doomed après tout"
        },
        {
            "name": "Bas Canada – Dépression saisonnière",
            "producer": "Brasserie du Bas Canada",
            "expected": "Dépression saisonnière"
        },
        {
            "name": "Sir John – No Escape",
            "producer": "Brasserie Sir John Brewing co.",
            "expected": "No Escape"
        },
        {
            "name": "Mille-Îles – Sure Citron & Gingembre",
            "producer": "Brasserie Mille Iles",
            "expected": "Sure Citron & Gingembre"
        },
        {
            "name": "Bas Canada – Maréchal",
            "producer": "Brasserie du Bas Canada",
            "expected": "Maréchal"
        },
        # Cas où le nom ne devrait PAS être nettoyé
        {
            "name": "La Belle IPA",
            "producer": "Brasserie XYZ",
            "expected": "La Belle IPA"  # Pas de changement
        },
        {
            "name": "Fardeau",
            "producer": "Messorem Bracitorium",
            "expected": "Fardeau"  # Pas de changement
        }
    ]

    print("="*60)
    print("🧪 TEST DE NETTOYAGE DES NOMS")
    print("="*60)

    passed = 0
    failed = 0

    for i, test in enumerate(test_beers, 1):
        print(f"\n{i}. {test['name']}")
        print(f"   Producteur: {test['producer']}")

        # Teste le nettoyage
        cleaned = cleaner.clean_beer_name(test)
        expected = test['expected']

        print(f"   Résultat:   {cleaned}")
        print(f"   Attendu:    {expected}")

        if cleaned == expected:
            print(f"   ✅ PASS")
            passed += 1
        else:
            print(f"   ❌ FAIL")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Résultats: {passed} tests réussis, {failed} tests échoués")
    print("="*60)


def test_edge_cases():
    """Teste des cas limites"""

    cleaner = BeerNameCleaner(dry_run=True)

    edge_cases = [
        {
            "description": "Séparateur tiret simple",
            "beer": {"name": "Trou du Diable - Saison", "producer": "Le Trou du Diable"},
            "expected": "Saison"
        },
        {
            "description": "Séparateur deux-points",
            "beer": {"name": "Dieu du Ciel: Péché Mortel", "producer": "Dieu du Ciel"},
            "expected": "Péché Mortel"
        },
        {
            "description": "Pas de séparateur",
            "beer": {"name": "Simple IPA", "producer": "Simple Brewery"},
            "expected": "Simple IPA"
        },
        {
            "description": "Préfixe court ignoré",
            "beer": {"name": "A – Test", "producer": "A Brewery"},
            "expected": "A – Test"
        },
        {
            "description": "Nom partiel du producteur",
            "beer": {"name": "Dieu – IPA", "producer": "Dieu du Ciel"},
            "expected": "IPA"
        }
    ]

    print("\n" + "="*60)
    print("🧪 TEST DE CAS LIMITES")
    print("="*60)

    passed = 0
    failed = 0

    for i, test in enumerate(edge_cases, 1):
        print(f"\n{i}. {test['description']}")
        print(f"   Nom:        {test['beer']['name']}")
        print(f"   Producteur: {test['beer']['producer']}")

        cleaned = cleaner.clean_beer_name(test['beer'])
        expected = test['expected']

        print(f"   Résultat:   {cleaned}")
        print(f"   Attendu:    {expected}")

        if cleaned == expected:
            print(f"   ✅ PASS")
            passed += 1
        else:
            print(f"   ❌ FAIL")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Résultats: {passed} tests réussis, {failed} tests échoués")
    print("="*60)


def test_detection():
    """Teste la détection des noms à nettoyer"""

    cleaner = BeerNameCleaner(dry_run=True)

    test_cases = [
        {
            "name": "Messorem – Not so doomed",
            "producer": "Messorem Bracitorium",
            "should_clean": True
        },
        {
            "name": "Fardeau",
            "producer": "Messorem Bracitorium",
            "should_clean": False
        },
        {
            "name": "La Belle IPA",
            "producer": "Simple Malt",
            "should_clean": False
        },
        {
            "name": "Simple – IPA",
            "producer": "Microbrasserie Simple",
            "should_clean": True
        }
    ]

    print("\n" + "="*60)
    print("🧪 TEST DE DÉTECTION")
    print("="*60)

    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['name']} ({test['producer']})")

        should_clean = cleaner.should_clean(test['name'], test['producer'])
        expected = test['should_clean']

        status = "OUI" if should_clean else "NON"
        expected_status = "OUI" if expected else "NON"

        print(f"   Doit nettoyer: {status} (attendu: {expected_status})")

        if should_clean == expected:
            print(f"   ✅ PASS")
        else:
            print(f"   ❌ FAIL")

    print("="*60)


if __name__ == "__main__":
    print("\n🍺 TEST DU NETTOYAGE DES NOMS DE BIÈRES\n")

    # Tests avec exemples réels
    test_cleaning()

    # Tests de cas limites
    test_edge_cases()

    # Tests de détection
    test_detection()
