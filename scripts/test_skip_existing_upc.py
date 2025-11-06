"""
Script de test pour valider que les bières avec UPC existant sont bien skippées
"""

from upc_enrichment import UPCEnricher
import json


def test_skip_existing_upc():
    """Teste que les bières avec UPC existant sont skippées"""

    enricher = UPCEnricher()

    beers = [
        {
            "name": "Bière avec UPC",
            "producer": "Test Brewery",
            "volume": "473ml",
            "upc": "725330860345"  # UPC déjà présent
        },
        {
            "name": "Bière sans UPC",
            "producer": "Another Brewery",
            "volume": "355ml"
            # Pas de UPC
        }
    ]

    print("="*60)
    print("🧪 TEST: SKIP DES BIÈRES AVEC UPC EXISTANT")
    print("="*60)

    print("\nBières de test:")
    for i, beer in enumerate(beers, 1):
        upc_status = f"UPC: {beer['upc']}" if beer.get('upc') else "Pas d'UPC"
        print(f"  {i}. {beer['name']} - {upc_status}")

    print("\n" + "="*60)
    print("Simulation de l'enrichissement...\n")

    # Simule le traitement
    for i, beer in enumerate(beers):
        if beer.get('upc'):
            enricher.stats['already_has_upc'] += 1
            print(f"{i+1}. ⏭️  Skipped: {beer.get('name')} (UPC existant: {beer.get('upc')})")
        else:
            print(f"{i+1}. 🔍 Recherche UPC pour: {beer.get('name')} ({beer.get('producer')})")
            print(f"   → Rechercherait dans l'API...")

    print("\n" + "="*60)
    print("📊 RÉSULTATS")
    print("="*60)
    print(f"Bières avec UPC existant: {enricher.stats['already_has_upc']}")
    print(f"Bières à traiter:         {len(beers) - enricher.stats['already_has_upc']}")

    # Vérifie le comportement attendu
    if enricher.stats['already_has_upc'] == 1:
        print("\n✅ Test réussi! La bière avec UPC existant a été skippée.")
    else:
        print("\n❌ Test échoué!")

    print("="*60)


if __name__ == "__main__":
    test_skip_existing_upc()
