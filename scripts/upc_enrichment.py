import json
import time
import urllib.parse
import urllib.request
import ssl
from pathlib import Path
from typing import Dict, List, Optional
import re

# Try to import requests (better HTTP handling)
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class UPCEnricher:
    """
    Enrichit les données de bières avec les codes UPC depuis l'API Consignaction
    """

    API_URL = "https://3mpn6qujk3-dsn.algolia.net/1/indexes/liste_dynamic"
    API_KEY = "43f2df5a9dbcda207c4bfdd521d739a9"
    APP_ID = "3MPN6QUJK3"

    def __init__(self, delay: float = 0.5):
        """
        Args:
            delay: Délai en secondes entre chaque requête API (pour éviter le rate limiting)
        """
        self.delay = delay
        self.stats = {
            'total': 0,
            'found': 0,
            'not_found': 0,
            'errors': 0,
            'already_has_upc': 0
        }

    def normalize_text(self, text: str) -> str:
        """Normalise le texte pour la comparaison"""
        if not text:
            return ""

        # Minuscules
        text = text.lower()

        # Enlève les mots courants des brasseries
        text = re.sub(r'\b(brasserie|microbrasserie|inc\.?|ltée|brewing|brewery)\b', '', text)

        # Enlève la ponctuation
        text = re.sub(r'[.,!?;:()\[\]{}"\'\\/-]', ' ', text)

        # Normalise les espaces
        text = ' '.join(text.split())

        return text.strip()

    def normalize_volume(self, volume: str) -> str:
        """Normalise le volume pour la comparaison"""
        if not volume:
            return ""

        # Extrait juste les chiffres et l'unité
        volume = volume.lower().strip()
        volume = re.sub(r'\s+', '', volume)  # Enlève les espaces

        return volume

    def is_exact_match(self, beer: Dict, api_result: Dict) -> bool:
        """
        Vérifie si le résultat de l'API correspond EXACTEMENT à la bière

        Critères de matching:
        1. Le producer doit matcher le Maker
        2. Le name doit matcher EXACTEMENT le product (pas juste un substring)
        3. Le volume doit matcher (si disponible)
        """

        # 1. Vérifie le producteur
        beer_producer = self.normalize_text(beer.get('producer', ''))
        api_maker = self.normalize_text(api_result.get('Maker', ''))

        if not beer_producer or not api_maker:
            return False

        # Le maker doit contenir tous les mots du producer (ou vice-versa)
        producer_words = set(beer_producer.split())
        maker_words = set(api_maker.split())

        # Au moins 70% des mots doivent matcher
        if producer_words and maker_words:
            overlap = len(producer_words & maker_words)
            min_words = min(len(producer_words), len(maker_words))
            if overlap < min_words * 0.7:
                return False

        # 2. Vérifie le nom du produit - MATCH EXACT requis
        beer_name = self.normalize_text(beer.get('name', ''))
        api_product = self.normalize_text(api_result.get('product', ''))

        if not beer_name or not api_product:
            return False

        # Le nom doit être EXACTEMENT le même, OU l'API peut avoir 1 mot de plus (le style)
        # Exemples acceptés:
        # - "blanche de fox" vs "blanche de fox blanche" ✓ (style ajouté)
        # - "pop gose the world" vs "pop gose the world gose" ✓ (style ajouté)
        # Exemples rejetés:
        # - "fardeau" vs "fardeau xtrm turbo" ✗ (2+ mots supplémentaires = variante)

        beer_words = beer_name.split()
        api_words = api_product.split()

        # Si le nom de l'API a plus de mots
        if len(api_words) > len(beer_words):
            # Vérifie que l'API commence par le nom de la bière
            if not api_product.startswith(beer_name):
                return False

            # Tolère 1 mot supplémentaire (probablement le style)
            # Rejette si 2+ mots supplémentaires (variante)
            extra_words = len(api_words) - len(beer_words)
            if extra_words > 1:
                return False

        # Si les noms ne sont pas identiques, vérifie si c'est accepté (style ajouté)
        if beer_name != api_product:
            # Si l'API n'a pas plus de mots, ce n'est pas un match
            if len(api_words) <= len(beer_words):
                return False

            # Vérifie que l'API commence par le nom de la bière
            if not api_product.startswith(beer_name):
                return False

        # 3. Vérifie le volume (optionnel mais recommandé)
        beer_volume = self.normalize_volume(beer.get('volume', ''))
        api_volume = self.normalize_volume(api_result.get('volume', ''))

        if beer_volume and api_volume:
            if beer_volume != api_volume:
                # Tolère de légères différences (ex: "473ml" vs "473 ml")
                if beer_volume.replace(' ', '') != api_volume.replace(' ', ''):
                    return False

        return True

    def search_upc(self, beer: Dict) -> Optional[str]:
        """
        Recherche le code UPC pour une bière via l'API Consignaction

        Returns:
            Le code UPC si trouvé, None sinon
        """

        # Construit la requête de recherche
        producer = beer.get('producer', '')
        name = beer.get('name', '')

        if not producer or not name:
            return None

        query = f"{producer} {name}"

        # Prépare les paramètres de l'URL
        params = {
            'query': query,
            'page': '0',
            'hitsPerPage': '50',
            'x-algolia-api-key': self.API_KEY,
            'x-algolia-application-id': self.APP_ID
        }

        # Headers pour l'API (simule un navigateur pour éviter le blocage)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://consignaction.ca/',
            'Origin': 'https://consignaction.ca',
            'Accept': 'application/json',
            'Accept-Language': 'fr-CA,fr;q=0.9,en;q=0.8'
        }

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            # Fait la requête
            if HAS_REQUESTS:
                # Utilise requests si disponible (meilleure gestion des certificats)
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
            else:
                # Fallback vers urllib avec désactivation de la vérification SSL
                # Crée un contexte SSL qui n'effectue pas de vérification
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                    data = json.loads(response.read().decode('utf-8'))

            # Analyse les résultats
            hits = data.get('hits', [])

            if not hits:
                return None

            # Cherche un match exact
            for hit in hits:
                if self.is_exact_match(beer, hit):
                    upc = hit.get('upc')
                    if upc:
                        print(f"  ✓ UPC trouvé: {upc} pour {name}")
                        return upc

            # Affiche les résultats qui n'ont pas matché (pour debug)
            if hits:
                print(f"  ⚠ {len(hits)} résultat(s) trouvé(s) mais aucun match exact pour: {name}")
                for i, hit in enumerate(hits[:3], 1):
                    print(f"    {i}. {hit.get('product')} ({hit.get('Maker')})")

                # Debug: montre pourquoi le premier résultat n'a pas matché
                if len(hits) > 0:
                    print(f"\n  🔍 Debug du premier résultat:")
                    first_hit = hits[0]
                    print(f"     Beer: '{beer.get('name')}' / '{beer.get('producer')}'")
                    print(f"     API:  '{first_hit.get('product')}' / '{first_hit.get('Maker')}'")

                    beer_name_norm = self.normalize_text(beer.get('name', ''))
                    api_product_norm = self.normalize_text(first_hit.get('product', ''))
                    beer_producer_norm = self.normalize_text(beer.get('producer', ''))
                    api_maker_norm = self.normalize_text(first_hit.get('Maker', ''))

                    print(f"     Normalized:")
                    print(f"       Name: '{beer_name_norm}' vs '{api_product_norm}' → Match: {beer_name_norm == api_product_norm}")
                    print(f"       Prod: '{beer_producer_norm}' vs '{api_maker_norm}'")

            return None

        except urllib.error.HTTPError as e:
            print(f"  ✗ Erreur HTTP {e.code} pour: {name}")
            return None
        except Exception as e:
            print(f"  ✗ Erreur lors de la recherche pour {name}: {e}")
            return None

    def enrich_beers(self, beers: List[Dict], start_index: int = 0) -> List[Dict]:
        """
        Enrichit la liste de bières avec les codes UPC

        Args:
            beers: Liste des bières à enrichir
            start_index: Index de départ (pour reprendre après une interruption)

        Returns:
            Liste des bières enrichies
        """

        self.stats['total'] = len(beers)

        print(f"\n🔍 Début de l'enrichissement des UPC...")
        print(f"   Total de bières: {len(beers)}")
        print(f"   Index de départ: {start_index}\n")

        for i in range(start_index, len(beers)):
            beer = beers[i]

            # Affiche la progression tous les 10 items
            if i % 10 == 0:
                print(f"\n📊 Progression: {i}/{len(beers)} ({i*100//len(beers)}%)")

            # Vérifie si la bière a déjà un UPC
            if beer.get('upc'):
                self.stats['already_has_upc'] += 1
                print(f"{i+1}. ⏭️  Skipped: {beer.get('name')} (UPC existant: {beer.get('upc')})")
                continue

            # Recherche le UPC
            print(f"{i+1}. 🔍 Recherche UPC pour: {beer.get('name')} ({beer.get('producer')})")

            upc = self.search_upc(beer)

            if upc:
                beer['upc'] = upc
                self.stats['found'] += 1
            else:
                self.stats['not_found'] += 1

            # Délai entre les requêtes
            time.sleep(self.delay)

        return beers

    def print_stats(self):
        """Affiche les statistiques finales"""
        print("\n" + "="*60)
        print("📊 STATISTIQUES FINALES")
        print("="*60)
        print(f"Total de bières:           {self.stats['total']}")
        print(f"Déjà avec UPC:             {self.stats['already_has_upc']}")
        print(f"UPC trouvés:               {self.stats['found']}")
        print(f"UPC non trouvés:           {self.stats['not_found']}")
        print(f"Erreurs:                   {self.stats['errors']}")

        if self.stats['total'] > 0:
            success_rate = (self.stats['found'] / (self.stats['total'] - self.stats['already_has_upc'])) * 100
            print(f"\nTaux de succès:            {success_rate:.1f}%")

        print("="*60)


def main():
    """Point d'entrée principal du script"""

    # Chemins des fichiers
    input_file = Path('../data/beers_merged.json')

    # Essaie aussi dans datas/
    if not input_file.exists():
        input_file = Path('../datas/beers_merged.json')

    if not input_file.exists():
        print("❌ Erreur: Fichier beers_merged.json introuvable!")
        print(f"   Cherché dans: ../data/ et ../datas/")
        return

    output_file = input_file  # Écrase le fichier original
    backup_file = input_file.parent / f"{input_file.stem}_backup.json"

    print("="*60)
    print("🍺 ENRICHISSEMENT DES UPC DEPUIS CONSIGNACTION")
    print("="*60)
    print(f"Fichier d'entrée:  {input_file}")
    print(f"Fichier de sortie: {output_file}")
    print(f"Fichier de backup: {backup_file}")
    if HAS_REQUESTS:
        print("Méthode HTTP:      requests (recommandé)")
    else:
        print("Méthode HTTP:      urllib (SSL non-vérifié)")
    print("="*60)

    # Charge les données
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            beers = json.load(f)
        print(f"✓ {len(beers)} bières chargées")
    except Exception as e:
        print(f"❌ Erreur lors du chargement du fichier: {e}")
        return

    # Crée un backup
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(beers, f, ensure_ascii=False, indent=2)
        print(f"✓ Backup créé: {backup_file}")
    except Exception as e:
        print(f"⚠ Impossible de créer le backup: {e}")

    # Enrichit les données
    enricher = UPCEnricher(delay=0.5)  # 0.5 secondes entre chaque requête

    try:
        enriched_beers = enricher.enrich_beers(beers)

        # Sauvegarde les résultats
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_beers, f, ensure_ascii=False, indent=2)

        print(f"\n✓ Données enrichies sauvegardées dans: {output_file}")

        # Affiche les statistiques
        enricher.print_stats()

    except KeyboardInterrupt:
        print("\n\n⚠ Interruption détectée!")
        print("   Sauvegarde des données partielles...")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(beers, f, ensure_ascii=False, indent=2)

        print(f"   Données partielles sauvegardées dans: {output_file}")
        enricher.print_stats()

    except Exception as e:
        print(f"\n❌ Erreur durant l'enrichissement: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
