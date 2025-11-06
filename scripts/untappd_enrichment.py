import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import re

# Try to import requests (required for POST requests)
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("⚠️  La librairie 'requests' est requise pour ce script.")
    print("   Installez-la avec: pip install requests")
    exit(1)


class UntappdEnricher:
    """
    Enrichit les données de bières avec les informations d'Untappd via l'API Algolia
    """

    API_URL = 'https://9wbo4rq3ho-dsn.algolia.net/1/indexes/beer/query'

    HEADERS = {
        'x-algolia-agent': 'Algolia for vanilla JavaScript 3.24.8',
        'x-algolia-application-id': '9WBO4RQ3HO',
        'x-algolia-api-key': '1d347324d67ec472bb7132c66aead485',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    def __init__(self, delay: float = 0.5, min_ratings: int = 5):
        """
        Args:
            delay: Délai en secondes entre chaque requête API
            min_ratings: Nombre minimum de ratings pour considérer un résultat valide
        """
        self.delay = delay
        self.min_ratings = min_ratings
        self.stats = {
            'total': 0,
            'found': 0,
            'not_found': 0,
            'errors': 0,
            'already_has_untappd': 0
        }

    def normalize_text(self, text: str) -> str:
        """Normalise le texte pour la comparaison"""
        if not text:
            return ""

        # Minuscules
        text = text.lower()

        # Enlève les accents
        import unicodedata
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')

        # Enlève les mots courants des brasseries
        stopwords = [
            'brasserie', 'microbrasserie', 'artisanal', 'artisanale',
            'brasseurs', 'brasseur', 'inc', 'ltd', 'ltée', 'ltee',
            'compagnie', 'company', 'co', 'brewing', 'brewery', 'microbrewery'
        ]

        for word in stopwords:
            text = re.sub(r'\b' + word + r'\b', '', text)

        # Enlève la ponctuation
        text = re.sub(r'[^a-z0-9\s]', ' ', text)

        # Normalise les espaces
        text = ' '.join(text.split())

        return text.strip()

    def tokens(self, text: str) -> list:
        """Découpe le texte en tokens"""
        return [t for t in self.normalize_text(text).split() if t]

    def token_overlap_ratio(self, text1: str, text2: str) -> float:
        """Calcule le ratio de tokens qui matchent"""
        tokens1 = set(self.tokens(text1))
        tokens2 = set(self.tokens(text2))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        return intersection / len(tokens1)

    def is_exact_match(self, beer: Dict, untappd_result: Dict) -> bool:
        """
        Vérifie si le résultat Untappd correspond EXACTEMENT à la bière

        Critères de matching:
        1. Le beer_name doit matcher le name de la bière (pas de mots supplémentaires)
        2. Le brewery_name doit matcher le producer
        3. Au moins 80% des tokens doivent matcher
        """

        # 1. Vérifie le nom de la bière
        beer_name = self.normalize_text(beer.get('name', ''))
        untappd_name = self.normalize_text(untappd_result.get('beer_name', ''))

        if not beer_name or not untappd_name:
            return False

        beer_tokens = set(self.tokens(beer.get('name', '')))
        untappd_tokens = set(self.tokens(untappd_result.get('beer_name', '')))

        # IMPORTANT: Rejette si l'API a des mots supplémentaires
        # Ex: "Fardeau" ne doit PAS matcher "Fardeau Xtrm Turbo"
        if len(untappd_tokens) > len(beer_tokens):
            # Vérifie si les tokens de la bière sont un subset exact
            if not beer_tokens.issubset(untappd_tokens):
                return False
            # Si l'API a plus de tokens, c'est une variante -> rejette
            extra_tokens = untappd_tokens - beer_tokens
            if extra_tokens:
                return False

        # Calcule le ratio de tokens qui matchent
        name_overlap = self.token_overlap_ratio(beer.get('name', ''), untappd_result.get('beer_name', ''))

        # Le nom doit avoir au moins 80% de tokens en commun
        if name_overlap < 0.8:
            return False

        # Les deux noms doivent avoir le même nombre de tokens (ou très proche)
        if abs(len(beer_tokens) - len(untappd_tokens)) > 1:
            return False

        # 2. Vérifie le producteur
        beer_producer = self.normalize_text(beer.get('producer', ''))
        untappd_brewery = self.normalize_text(untappd_result.get('brewery_name', ''))

        if beer_producer and untappd_brewery:
            producer_overlap = self.token_overlap_ratio(beer.get('producer', ''), untappd_result.get('brewery_name', ''))

            # Le producteur doit avoir au moins 60% de tokens en commun
            if producer_overlap < 0.6:
                return False

        return True

    def build_query_candidates(self, producer: str, name: str) -> List[str]:
        """Génère plusieurs candidats de requête"""
        candidates = []

        if producer and name:
            candidates.append(f"{producer} {name}")
            candidates.append(f"{name} {producer}")
            candidates.append(name)
        elif name:
            candidates.append(name)
        elif producer:
            candidates.append(producer)

        return candidates

    def search_untappd(self, beer: Dict) -> Optional[Dict]:
        """
        Recherche les données Untappd pour une bière via l'API Algolia

        Returns:
            Les données Untappd si trouvées, None sinon
        """

        producer = beer.get('producer', '')
        name = beer.get('name', '')

        if not name:
            return None

        # Génère plusieurs candidats de requête
        query_candidates = self.build_query_candidates(producer, name)

        for query in query_candidates:
            if not query:
                continue

            try:
                # Prépare le payload
                payload = {
                    'query': query,
                    'hitsPerPage': 12
                }

                # Fait la requête POST
                response = requests.post(
                    self.API_URL,
                    json=payload,
                    headers=self.HEADERS,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()

                # Analyse les résultats
                hits = data.get('hits', [])

                if not hits:
                    continue

                # Filtre les hits avec un minimum de ratings
                valid_hits = [
                    hit for hit in hits
                    if hit.get('beer_name') and int(hit.get('rating_count', 0)) >= self.min_ratings
                ]

                if not valid_hits:
                    continue

                # Cherche un match exact
                for hit in valid_hits:
                    if self.is_exact_match(beer, hit):
                        print(f"  ✓ Match Untappd: {hit.get('beer_name')} ({hit.get('brewery_name')})")
                        print(f"    Rating: {hit.get('rating_score', 0):.2f} ({hit.get('rating_count', 0)} ratings)")
                        return self.extract_untappd_data(hit)

                # Si pas de match exact, affiche les résultats
                print(f"  ⚠ {len(valid_hits)} résultat(s) trouvé(s) mais aucun match exact")
                for i, hit in enumerate(valid_hits[:3], 1):
                    print(f"    {i}. {hit.get('beer_name')} ({hit.get('brewery_name')})")

            except requests.exceptions.RequestException as e:
                print(f"  ✗ Erreur API pour {name}: {e}")
                continue
            except Exception as e:
                print(f"  ✗ Erreur lors de la recherche pour {name}: {e}")
                continue

            # Délai entre les requêtes
            time.sleep(self.delay)

        return None

    def extract_untappd_data(self, hit: Dict) -> Dict:
        """Extrait les données pertinentes d'un hit Untappd"""

        bid = hit.get('bid')
        beer_slug = hit.get('beer_slug', '')
        brewery_slug = hit.get('brewery_slug', '')

        # Construit l'URL Untappd
        url = None
        if bid:
            if brewery_slug and beer_slug:
                url = f"https://untappd.com/b/{brewery_slug}-{beer_slug}/{bid}"
            elif beer_slug:
                url = f"https://untappd.com/b/{beer_slug}/{bid}"
            else:
                url = f"https://untappd.com/b/_/{bid}"

        return {
            'untappd_id': bid,
            'untappd_url': url,
            'untappd_name': hit.get('beer_name'),
            'untappd_brewery': hit.get('brewery_name'),
            'untappd_style': hit.get('beer_style'),
            'untappd_abv': hit.get('beer_abv'),
            'untappd_ibu': hit.get('beer_ibu'),
            'untappd_rating': hit.get('rating_score'),
            'untappd_rating_count': hit.get('rating_count'),
            'untappd_description': hit.get('beer_description'),
            'untappd_label': hit.get('beer_label')
        }

    def enrich_beers(self, beers: List[Dict], start_index: int = 0) -> List[Dict]:
        """
        Enrichit la liste de bières avec les données Untappd

        Args:
            beers: Liste des bières à enrichir
            start_index: Index de départ (pour reprendre après une interruption)

        Returns:
            Liste des bières enrichies
        """

        self.stats['total'] = len(beers)

        print(f"\n🍺 Début de l'enrichissement Untappd...")
        print(f"   Total de bières: {len(beers)}")
        print(f"   Index de départ: {start_index}\n")

        for i in range(start_index, len(beers)):
            beer = beers[i]

            # Affiche la progression tous les 10 items
            if i % 10 == 0:
                print(f"\n📊 Progression: {i}/{len(beers)} ({i*100//len(beers)}%)")

            # Vérifie si la bière a déjà des données Untappd
            if beer.get('untappd_id'):
                self.stats['already_has_untappd'] += 1
                print(f"{i+1}. ⏭️  Skipped: {beer.get('name')} (Untappd ID existant: {beer.get('untappd_id')})")
                continue

            # Recherche sur Untappd
            print(f"{i+1}. 🔍 Recherche Untappd pour: {beer.get('name')} ({beer.get('producer')})")

            untappd_data = self.search_untappd(beer)

            if untappd_data:
                # Ajoute les données Untappd à la bière
                beer.update(untappd_data)
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
        print(f"Déjà avec Untappd:         {self.stats['already_has_untappd']}")
        print(f"Données trouvées:          {self.stats['found']}")
        print(f"Non trouvées:              {self.stats['not_found']}")
        print(f"Erreurs:                   {self.stats['errors']}")

        if self.stats['total'] > 0:
            to_process = self.stats['total'] - self.stats['already_has_untappd']
            if to_process > 0:
                success_rate = (self.stats['found'] / to_process) * 100
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
    backup_file = input_file.parent / f"{input_file.stem}_untappd_backup.json"

    print("="*60)
    print("🍺 ENRICHISSEMENT UNTAPPD")
    print("="*60)
    print(f"Fichier d'entrée:  {input_file}")
    print(f"Fichier de sortie: {output_file}")
    print(f"Fichier de backup: {backup_file}")
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
    enricher = UntappdEnricher(delay=0.5, min_ratings=5)

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
