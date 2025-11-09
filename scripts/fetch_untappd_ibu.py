#!/usr/bin/env python3
"""
Script pour récupérer les IBU depuis Untappd via l'API Algolia
Usage: python scripts/fetch_untappd_ibu.py <input_file> [output_file]
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
import re

try:
    import requests
except ImportError:
    print("❌ La librairie 'requests' est requise.")
    print("   Installez-la avec: pip install requests")
    sys.exit(1)

# Try to import Selenium (for scraping IBU from page)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from bs4 import BeautifulSoup
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False
    print("⚠️  Selenium et BeautifulSoup4 sont recommandés pour récupérer les IBU depuis les pages.")
    print("   Installez-les avec: pip install selenium beautifulsoup4")
    print("   Le script continuera avec l'API seulement (données limitées).\n")


class UntappdIBUFetcher:
    """Récupère les IBU depuis Untappd"""

    API_URL = 'https://9wbo4rq3ho-dsn.algolia.net/1/indexes/beer/query'

    HEADERS = {
        'x-algolia-agent': 'Algolia for vanilla JavaScript 3.24.8',
        'x-algolia-application-id': '9WBO4RQ3HO',
        'x-algolia-api-key': '1d347324d67ec472bb7132c66aead485',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    def __init__(self, delay: float = 0.5, min_ratings: int = 5, use_selenium: bool = True):
        """
        Args:
            delay: Délai en secondes entre chaque requête API
            min_ratings: Nombre minimum de ratings pour considérer un résultat valide
            use_selenium: Si True, utilise Selenium pour scraper l'IBU depuis la page
        """
        self.delay = delay
        self.min_ratings = min_ratings
        self.use_selenium = use_selenium and HAS_SELENIUM
        self.driver = None

        # Initialise le driver Selenium si disponible
        if self.use_selenium:
            try:
                chrome_options = Options()
                chrome_options.add_argument('--headless')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                self.driver = webdriver.Chrome(options=chrome_options)
                print("✓ Selenium activé pour scraping des IBU depuis les pages web")
            except Exception as e:
                print(f"⚠️ Impossible d'initialiser Selenium: {e}")
                print("   Le script continuera avec l'API seulement (données limitées)\n")
                self.use_selenium = False
                self.driver = None

        self.stats = {
            'total': 0,
            'skipped': 0,
            'found': 0,
            'scraped': 0,
            'not_found': 0,
            'errors': 0
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
        """Vérifie si le résultat Untappd correspond à la bière"""

        # Vérifie le nom de la bière
        beer_name = self.normalize_text(beer.get('name', ''))
        untappd_name = self.normalize_text(untappd_result.get('beer_name', ''))

        if not beer_name or not untappd_name:
            return False

        beer_tokens = set(self.tokens(beer.get('name', '')))
        untappd_tokens = set(self.tokens(untappd_result.get('beer_name', '')))

        # Rejette si l'API a des mots supplémentaires
        if len(untappd_tokens) > len(beer_tokens):
            if not beer_tokens.issubset(untappd_tokens):
                return False
            extra_tokens = untappd_tokens - beer_tokens
            if extra_tokens:
                return False

        # Le nom doit avoir au moins 80% de tokens en commun
        name_overlap = self.token_overlap_ratio(beer.get('name', ''), untappd_result.get('beer_name', ''))
        if name_overlap < 0.8:
            return False

        # Les deux noms doivent avoir le même nombre de tokens (ou très proche)
        if abs(len(beer_tokens) - len(untappd_tokens)) > 1:
            return False

        # Vérifie le producteur si disponible
        beer_producer = self.normalize_text(beer.get('producer', ''))
        untappd_brewery = self.normalize_text(untappd_result.get('brewery_name', ''))

        if beer_producer and untappd_brewery:
            producer_overlap = self.token_overlap_ratio(beer.get('producer', ''), untappd_result.get('brewery_name', ''))
            # Le producteur doit avoir au moins 60% de tokens en commun
            if producer_overlap < 0.6:
                return False

        return True

    def scrape_ibu_from_page(self, url: str) -> Optional[int]:
        """
        Scrape l'IBU depuis la page Untappd

        Args:
            url: URL de la page Untappd

        Returns:
            La valeur IBU si trouvée, None sinon
        """
        if not self.driver or not url:
            return None

        try:
            self.driver.get(url)
            time.sleep(2)  # Attendre le chargement du JavaScript

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Cherche l'IBU dans la page
            # Format : <p class="ibu">5 IBU</p>
            ibu_elem = soup.find('p', {'class': 'ibu'})
            if ibu_elem:
                ibu_text = ibu_elem.get_text(strip=True)
                # Extrait le nombre depuis "5 IBU" ou "25 IBU"
                match = re.search(r'(\d+)\s*IBU', ibu_text)
                if match:
                    ibu = int(match.group(1))
                    print(f"    🔍 IBU scrapé depuis la page: {ibu}")
                    return ibu

            return None

        except Exception as e:
            print(f"    ⚠️ Erreur lors du scraping de {url}: {e}")
            return None

    def search_untappd_ibu(self, beer: Dict) -> Optional[int]:
        """
        Recherche l'IBU sur Untappd pour une bière

        Returns:
            La valeur IBU si trouvée, None sinon
        """
        producer = beer.get('producer', '')
        name = beer.get('name', '')

        if not name:
            return None

        # Génère plusieurs candidats de requête
        query_candidates = []
        if producer and name:
            query_candidates.append(f"{producer} {name}")
            query_candidates.append(f"{name} {producer}")
            query_candidates.append(name)
        elif name:
            query_candidates.append(name)

        for query in query_candidates:
            if not query:
                continue

            try:
                # Requête POST à l'API Algolia
                payload = {
                    'query': query,
                    'hitsPerPage': 12
                }

                response = requests.post(
                    self.API_URL,
                    json=payload,
                    headers=self.HEADERS,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()

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
                        ibu = hit.get('beer_ibu')

                        # Si l'IBU est présent dans l'API, le retourner
                        if ibu is not None:
                            print(f"  ✓ IBU trouvé (API): {ibu} - {hit.get('beer_name')} ({hit.get('brewery_name')})")
                            return ibu

                        # Si l'IBU est absent de l'API mais qu'on a Selenium, scraper la page
                        if self.use_selenium:
                            # Construit l'URL Untappd
                            bid = hit.get('bid')
                            beer_slug = hit.get('beer_slug', '')
                            brewery_slug = hit.get('brewery_slug', '')

                            if bid:
                                if brewery_slug and beer_slug:
                                    url = f"https://untappd.com/b/{brewery_slug}-{beer_slug}/{bid}"
                                elif beer_slug:
                                    url = f"https://untappd.com/b/{beer_slug}/{bid}"
                                else:
                                    url = f"https://untappd.com/b/_/{bid}"

                                print(f"  ⚠ Match trouvé mais pas d'IBU dans l'API: {hit.get('beer_name')}")
                                print(f"  🔍 Scraping de la page: {url}")

                                ibu = self.scrape_ibu_from_page(url)
                                if ibu is not None:
                                    self.stats['scraped'] += 1
                                    return ibu
                        else:
                            print(f"  ⚠ Match trouvé mais pas d'IBU: {hit.get('beer_name')} (scraping désactivé)")

                        return None

            except requests.exceptions.RequestException as e:
                print(f"  ✗ Erreur API: {e}")
                continue
            except Exception as e:
                print(f"  ✗ Erreur: {e}")
                continue

            # Délai entre les requêtes
            time.sleep(self.delay)

        return None

    def fetch_ibus(self, beers: List[Dict], start_index: int = 0) -> List[Dict]:
        """
        Récupère les IBU pour toutes les bières

        Args:
            beers: Liste des bières
            start_index: Index de départ (pour reprendre après interruption)

        Returns:
            Liste des bières avec IBU ajouté
        """
        self.stats['total'] = len(beers)

        print(f"\n🍺 Récupération des IBU depuis Untappd...")
        print(f"   Total de bières: {len(beers)}")
        print(f"   Index de départ: {start_index}\n")

        for i in range(start_index, len(beers)):
            beer = beers[i]

            # Progression tous les 10 items
            if i % 10 == 0 and i > 0:
                print(f"\n📊 Progression: {i}/{len(beers)} ({i*100//len(beers)}%)")

            # Skip si IBU déjà présent
            if beer.get('untappd_ibu') is not None:
                self.stats['skipped'] += 1
                print(f"{i+1}. ⏭️  Skipped: {beer.get('name')} (IBU déjà présent: {beer.get('untappd_ibu')})")
                continue

            # Recherche l'IBU
            print(f"{i+1}. 🔍 Recherche IBU pour: {beer.get('name')} ({beer.get('producer', 'N/A')})")

            ibu = self.search_untappd_ibu(beer)

            if ibu is not None:
                beer['untappd_ibu'] = ibu
                self.stats['found'] += 1
            else:
                self.stats['not_found'] += 1
                print(f"  ✗ IBU non trouvé")

            # Délai entre les bières
            time.sleep(self.delay)

        return beers

    def cleanup(self):
        """Ferme le driver Selenium proprement"""
        if self.driver:
            try:
                self.driver.quit()
                print("\n✓ Driver Selenium fermé")
            except Exception as e:
                print(f"\n⚠️ Erreur lors de la fermeture du driver: {e}")

    def __del__(self):
        """Destructeur - ferme le driver si encore ouvert"""
        self.cleanup()

    def print_stats(self):
        """Affiche les statistiques"""
        print("\n" + "="*60)
        print("📊 STATISTIQUES FINALES")
        print("="*60)
        print(f"Total de bières:           {self.stats['total']}")
        print(f"IBU déjà présents:         {self.stats['skipped']}")
        print(f"IBU trouvés:               {self.stats['found']}")
        if self.use_selenium:
            print(f"  - depuis l'API:          {self.stats['found'] - self.stats['scraped']}")
            print(f"  - scrapés depuis pages:  {self.stats['scraped']}")
        print(f"IBU non trouvés:           {self.stats['not_found']}")
        print(f"Erreurs:                   {self.stats['errors']}")

        if self.stats['total'] > 0:
            processed = self.stats['total'] - self.stats['skipped']
            if processed > 0:
                success_rate = (self.stats['found'] / processed) * 100
                print(f"\nTaux de succès:            {success_rate:.1f}%")

        print("="*60)


def main():
    """Point d'entrée du script"""

    if len(sys.argv) < 2:
        print("Usage: python scripts/fetch_untappd_ibu.py <input_file> [output_file]")
        print("Exemple: python scripts/fetch_untappd_ibu.py data/beers_cleaned.json")
        sys.exit(1)

    input_file = Path(sys.argv[1])

    # Fichier de sortie (même fichier si non spécifié)
    if len(sys.argv) >= 3:
        output_file = Path(sys.argv[2])
    else:
        output_file = input_file

    # Vérifie que le fichier existe
    if not input_file.exists():
        print(f"❌ Erreur: Fichier {input_file} introuvable!")
        sys.exit(1)

    # Backup
    backup_file = input_file.parent / f"{input_file.stem}_ibu_backup.json"

    print("="*60)
    print("🍺 RÉCUPÉRATION IBU DEPUIS UNTAPPD")
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
        print(f"❌ Erreur lors du chargement: {e}")
        sys.exit(1)

    # Crée un backup
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(beers, f, ensure_ascii=False, indent=2)
        print(f"✓ Backup créé: {backup_file}")
    except Exception as e:
        print(f"⚠ Impossible de créer le backup: {e}")

    # Récupère les IBU
    fetcher = UntappdIBUFetcher(delay=0.5, min_ratings=5, use_selenium=True)

    try:
        enriched_beers = fetcher.fetch_ibus(beers)

        # Sauvegarde
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_beers, f, ensure_ascii=False, indent=2)

        print(f"\n✓ Données sauvegardées dans: {output_file}")
        fetcher.print_stats()

    except KeyboardInterrupt:
        print("\n\n⚠ Interruption détectée!")
        print("   Sauvegarde des données partielles...")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(beers, f, ensure_ascii=False, indent=2)

        print(f"   Données partielles sauvegardées dans: {output_file}")
        fetcher.print_stats()

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Ferme le driver Selenium proprement
        fetcher.cleanup()


if __name__ == "__main__":
    main()
