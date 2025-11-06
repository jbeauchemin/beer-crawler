#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal Beer Crawler - Crawler adaptatif pour n'importe quel site de microbrasserie
S'adapte automatiquement à la structure du site et extrait les données intelligemment
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import time
import json
import re
from collections import Counter
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Set

# Import webdriver-manager pour installation automatique de ChromeDriver
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False
    print("⚠️  webdriver-manager non installé. Installation automatique de ChromeDriver désactivée.")
    print("   Pour l'activer: pip install webdriver-manager")


class UniversalBeerCrawler:
    """
    Crawler universel qui s'adapte automatiquement à n'importe quel site de brasserie
    """

    def __init__(self, base_url: str, headless: bool = True, verbose: bool = False):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.beers = []
        self.verbose = verbose

        # Configuration Chrome
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        # Initialise Chrome avec webdriver-manager si disponible
        if WEBDRIVER_MANAGER_AVAILABLE:
            try:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e:
                print(f"⚠️  Erreur avec webdriver-manager: {e}")
                print("   Tentative avec ChromeDriver par défaut...")
                self.driver = webdriver.Chrome(options=chrome_options)
        else:
            self.driver = webdriver.Chrome(options=chrome_options)

        self.wait = WebDriverWait(self.driver, 10)

        # Configuration découverte automatiquement
        self.config = {
            'platform': None,
            'product_url_pattern': None,
            'listing_pages': [],
            'selectors': {
                'name': [],
                'price': [],
                'description': [],
                'photo': [],
                'alcohol': [],
                'volume': [],
                'producer': [],
                'style': []
            }
        }

    # ============================================================================
    # DÉTECTION DE PLATEFORME
    # ============================================================================

    def detect_platform(self, soup: BeautifulSoup) -> str:
        """Détecte la plateforme du site"""
        html = str(soup).lower()

        if 'shopify' in html or 'cdn.shopify.com' in html:
            return 'Shopify'
        elif 'woocommerce' in html:
            return 'WooCommerce'
        elif 'wp-content' in html or 'wordpress' in html:
            return 'WordPress'
        elif 'squarespace' in html:
            return 'Squarespace'
        else:
            return 'Custom'

    # ============================================================================
    # DÉTECTION D'URLs
    # ============================================================================

    def is_product_url(self, url: str) -> bool:
        """Détermine si une URL pointe vers une page produit"""
        # Exclut les pages de collection/catégorie avec paramètres
        if re.search(r'[?&](page|sort|filter|limit|collection)=', url, re.I):
            return False

        # Patterns de produits
        product_patterns = [
            r'/products?/[^/]+/?$',
            r'/produits?/[^/]+/?$',
            r'/biere[s]?/[^/]+/?$',
            r'/beer[s]?/[^/]+/?$',
            r'/boutique/[^/]+/?$',
            r'/shop/[^/]+/?$',
        ]

        for pattern in product_patterns:
            if re.search(pattern, url, re.I):
                return True

        return False

    def is_beer_related_collection(self, url: str) -> bool:
        """Vérifie si une collection est liée aux bières (pas vêtements, verres, etc.)"""
        url_lower = url.lower()

        # Collections de bière (à inclure)
        beer_keywords = ['biere', 'beer', 'ale', 'ipa', 'stout', 'lager', 'brew']

        # Collections non-bière (à exclure)
        non_beer_keywords = [
            'vetement', 'clothing', 'apparel', 'shirt', 't-shirt', 'hoodie',
            'tuque', 'casquette', 'hat', 'cap', 'bonnet',
            'verre', 'glass', 'cup', 'mug',
            'accessoire', 'accessory', 'merchandise', 'merch',
            'cadeau', 'gift', 'carte', 'card'
        ]

        # Si contient un mot-clé non-bière, exclure
        for keyword in non_beer_keywords:
            if keyword in url_lower:
                return False

        # Si contient un mot-clé bière, inclure
        for keyword in beer_keywords:
            if keyword in url_lower:
                return True

        # Par défaut, si c'est une collection sans mot-clé spécifique, on l'inclut
        # (pour les sites qui ont juste /collections/all ou /products)
        return True

    def is_listing_url(self, url: str) -> bool:
        """Détermine si une URL est une page de liste de produits"""
        listing_patterns = [
            r'/products?/?(\?|$)',
            r'/produits?/?(\?|$)',
            r'/biere[s]?/?(\?|$)',
            r'/beer[s]?/?(\?|$)',
            r'/boutique/?(\?|$)',
            r'/shop/?(\?|$)',
            r'/collections?/',
            r'/catalogue/?(\?|$)',
        ]

        for pattern in listing_patterns:
            if re.search(pattern, url, re.I):
                # Si c'est une collection, vérifier que c'est lié aux bières
                if '/collection' in url.lower():
                    return self.is_beer_related_collection(url)
                return True

        return False

    def normalize_url(self, href: str) -> Optional[str]:
        """Normalise une URL"""
        if not href or href.startswith('#') or href.startswith('javascript:'):
            return None

        # Construit l'URL complète
        if href.startswith('http'):
            url = href
        elif href.startswith('/'):
            url = self.base_url + href
        else:
            return None  # Ignore les URLs relatives complexes

        # Garde seulement le même domaine (ou sous-domaines)
        url_domain = urlparse(url).netloc
        base_domain = '.'.join(self.domain.split('.')[-2:])  # ex: dieuduciel.com
        url_base_domain = '.'.join(url_domain.split('.')[-2:])

        if base_domain != url_base_domain:
            return None

        # Nettoie
        url = url.split('#')[0]  # Retire ancres

        # Pour les produits, retire les paramètres
        if self.is_product_url(url):
            url = url.split('?')[0]

        return url.rstrip('/')

    # ============================================================================
    # DÉCOUVERTE DE PRODUITS
    # ============================================================================

    def discover_product_links(self) -> List[str]:
        """Découvre tous les liens de produits du site"""
        print(f"\n📋 Découverte des produits sur {self.base_url}\n")

        product_links = set()
        listing_pages = set()

        # 1. Analyse homepage
        print("🏠 Analyse de la page d'accueil...")
        self.driver.get(self.base_url)
        time.sleep(3)
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')

        # Détecte plateforme
        self.config['platform'] = self.detect_platform(soup)
        print(f"   ✓ Plateforme: {self.config['platform']}")

        # Trouve tous les liens
        filtered_collections = []
        all_collection_urls = []
        all_urls_found = []

        for a in soup.find_all('a', href=True):
            href = a['href']
            url = self.normalize_url(href)

            # Debug: sauvegarder tous les liens
            if self.verbose and url:
                all_urls_found.append(url)

            if not url:
                continue

            # Debug: afficher les collections trouvées
            if '/collection' in url.lower():
                all_collection_urls.append(url)

            if self.is_product_url(url):
                product_links.add(url)
            elif '/collection' in url.lower():
                # C'est une collection, vérifions si c'est lié aux bières
                if self.is_beer_related_collection(url):
                    listing_pages.add(url)
                else:
                    # Collection filtrée (pas de bière)
                    collection_name = url.split('/')[-1]
                    filtered_collections.append(collection_name)
            elif self.is_listing_url(url):
                listing_pages.add(url)

        # Debug: afficher toutes les URLs trouvées
        if self.verbose:
            print(f"\n   🔍 DEBUG: {len(set(all_urls_found))} URLs uniques trouvées sur homepage")
            print(f"   🔍 DEBUG: {len(set(all_collection_urls))} collections détectées")
            if all_collection_urls:
                print(f"   🔍 Collections trouvées:")
                for col_url in sorted(set(all_collection_urls))[:10]:
                    is_beer = "✓ BIÈRE" if self.is_beer_related_collection(col_url) else "✗ FILTRÉ"
                    print(f"      {is_beer}: {col_url}")
            else:
                print("   🔍 Aucune collection trouvée. Exemples de liens:")
                for url in sorted(set(all_urls_found))[:15]:
                    print(f"      - {url}")

        print(f"\n   ✓ {len(product_links)} produits trouvés sur homepage")
        print(f"   ✓ {len(listing_pages)} pages de listing trouvées")
        if filtered_collections:
            unique_filtered = list(set(filtered_collections))[:5]
            print(f"   ⊘ {len(set(filtered_collections))} collections filtrées (non-bière): {', '.join(unique_filtered)}")

        # 2. Explore les pages de listing
        for listing_url in sorted(listing_pages):
            print(f"\n📄 Exploration: {listing_url}")
            products = self._crawl_listing_page(listing_url)
            product_links.update(products)
            print(f"   ✓ {len(products)} produits trouvés")

        self.config['listing_pages'] = sorted(listing_pages)

        print(f"\n✅ Total: {len(product_links)} produits découverts\n")

        # Sauvegarde les liens pour debug
        with open('product_links_discovered.txt', 'w', encoding='utf-8') as f:
            for link in sorted(product_links):
                f.write(link + '\n')

        return sorted(product_links)

    def _crawl_listing_page(self, url: str, max_pages: int = 50) -> Set[str]:
        """Crawle une page de listing et sa pagination"""
        products = set()
        visited = set()
        to_visit = [url]

        while to_visit and len(visited) < max_pages:
            current_url = to_visit.pop(0)

            if current_url in visited:
                continue

            visited.add(current_url)

            try:
                self.driver.get(current_url)
                time.sleep(2)
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                # Trouve produits
                page_products = set()
                for a in soup.find_all('a', href=True):
                    product_url = self.normalize_url(a['href'])
                    if product_url and self.is_product_url(product_url):
                        page_products.add(product_url)
                        products.add(product_url)

                # Si aucun produit, c'est probablement la fin
                if not page_products:
                    break

                # Trouve pagination
                for a in soup.find_all('a', href=True):
                    text = a.get_text(strip=True)
                    href = a.get('href', '')

                    # Liens "next", "suivant", etc.
                    if any(x in text.lower() for x in ['next', 'suivant', '›', '»', 'prochain']):
                        next_url = self.normalize_url(href)
                        if next_url and next_url not in visited and next_url not in to_visit:
                            to_visit.append(next_url)

            except Exception as e:
                print(f"      ⚠️  Erreur: {e}")
                continue

        return products

    # ============================================================================
    # EXTRACTION INTELLIGENTE
    # ============================================================================

    def extract_beer_data(self, url: str) -> Optional[Dict]:
        """Extrait les données d'une bière avec détection intelligente"""
        try:
            self.driver.get(url)
            time.sleep(2)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            beer = {
                'url': url,
                'name': None,
                'price': None,
                'producer': None,
                'style': None,
                'sub_style': None,
                'volume': None,
                'alcohol': None,
                'ibu': None,
                'description': None,
                'photo_url': None,
                '_extraction_methods': {}  # Pour debug
            }

            # NOM
            beer['name'], beer['_extraction_methods']['name'] = self._extract_name(soup)

            # PRIX
            beer['price'], beer['_extraction_methods']['price'] = self._extract_price(soup)

            # DESCRIPTION
            beer['description'], beer['_extraction_methods']['description'] = self._extract_description(soup)

            # PHOTO
            beer['photo_url'], beer['_extraction_methods']['photo'] = self._extract_photo(soup)

            # MÉTADONNÉES (alcool, volume, IBU, etc.)
            metadata = self._extract_metadata(soup)
            beer.update(metadata)

            # PRODUCTEUR / STYLE
            cat_data = self._extract_categories(soup)
            if cat_data.get('producer'):
                beer['producer'] = cat_data['producer']
            if cat_data.get('style'):
                beer['style'] = cat_data['style']
            if cat_data.get('sub_style'):
                beer['sub_style'] = cat_data['sub_style']

            return beer

        except Exception as e:
            print(f"  ✗ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_name(self, soup: BeautifulSoup) -> tuple:
        """Extrait le nom de la bière"""
        # 1. h1
        h1 = soup.find('h1')
        if h1:
            name = h1.get_text(strip=True)
            if name:
                return name, 'h1'

        # 2. og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'], 'og:title'

        # 3. title
        title = soup.find('title')
        if title:
            return title.get_text(strip=True), 'title'

        return None, None

    def _extract_price(self, soup: BeautifulSoup) -> tuple:
        """Extrait le prix"""
        # Cherche dans plusieurs endroits
        candidates = []

        # 1. Éléments avec class="price"
        for elem in soup.find_all(class_=re.compile(r'price', re.I)):
            text = elem.get_text(strip=True)
            if any(c in text for c in ['$', 'CAD', '€']) and len(text) < 30:
                candidates.append((text, f"class={elem.get('class')}"))

        # 2. itemprop="price"
        price_elem = soup.find(attrs={'itemprop': 'price'})
        if price_elem:
            text = price_elem.get_text(strip=True)
            if text:
                candidates.append((text, 'itemprop=price'))

        # 3. data-price
        price_elem = soup.find(attrs={'data-price': True})
        if price_elem:
            text = price_elem.get_text(strip=True) or price_elem.get('data-price', '')
            if text:
                candidates.append((text, 'data-price'))

        # Prend le premier candidat valide
        for price, method in candidates:
            # Valide que ça ressemble à un prix
            if re.search(r'\d+[.,]\d{2}', price):
                return price, method

        return None, None

    def _extract_description(self, soup: BeautifulSoup) -> tuple:
        """Extrait la description"""
        # 1. class="description"
        for elem in soup.find_all(class_=re.compile(r'description', re.I)):
            text = elem.get_text(strip=True)
            if text and len(text) > 30:  # Description raisonnable
                return text, f"class={elem.get('class')}"

        # 2. itemprop="description"
        desc_elem = soup.find(attrs={'itemprop': 'description'})
        if desc_elem:
            text = desc_elem.get_text(strip=True)
            if text and len(text) > 30:
                return text, 'itemprop=description'

        # 3. id="description" ou similaire
        for elem in soup.find_all(id=re.compile(r'description|desc', re.I)):
            text = elem.get_text(strip=True)
            if text and len(text) > 30:
                return text, f"id={elem.get('id')}"

        return None, None

    def _extract_photo(self, soup: BeautifulSoup) -> tuple:
        """Extrait l'URL de la photo principale"""
        # 1. og:image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            url = og_image['content'].split('?')[0]
            return url, 'og:image'

        # 2. Images dans galerie produit
        for class_pattern in [r'product.*image', r'gallery', r'main.*image']:
            img = soup.find('img', class_=re.compile(class_pattern, re.I))
            if img:
                url = img.get('data-src') or img.get('data-large_image') or img.get('src')
                if url:
                    url = url.split('?')[0]
                    if url.startswith('//'):
                        url = 'https:' + url
                    elif url.startswith('/'):
                        url = self.base_url + url
                    return url, f"img.{img.get('class')}"

        return None, None

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """Extrait les métadonnées (alcool, volume, IBU, etc.)"""
        metadata = {
            'alcohol': None,
            'volume': None,
            'ibu': None,
        }

        # Parcourt tous les éléments textuels
        for elem in soup.find_all(['li', 'div', 'p', 'span', 'td', 'th', 'dt', 'dd']):
            text = elem.get_text(' ', strip=True)

            # ALCOOL (%)
            if not metadata['alcohol']:
                match = re.search(r'(\d+\.?\d*)\s*%', text)
                if match:
                    alc = float(match.group(1))
                    # Valide que c'est de l'alcool (0-20%)
                    if 0 <= alc <= 20:
                        # Vérifie contexte (pas une remise/rabais)
                        lower_text = text.lower()
                        if not any(word in lower_text for word in ['rabais', 'remise', 'réduction', 'discount', 'off']):
                            metadata['alcohol'] = match.group(1) + '%'

            # VOLUME (ml)
            if not metadata['volume']:
                match = re.search(r'(\d{2,5})\s*ml', text, re.I)
                if match:
                    vol = int(match.group(1))
                    # Valide volume raisonnable (100ml - 5000ml)
                    if 100 <= vol <= 5000:
                        metadata['volume'] = match.group(1) + 'ml'

            # IBU
            if not metadata['ibu']:
                match = re.search(r'(\d+)\s*IBU', text, re.I)
                if match:
                    ibu = int(match.group(1))
                    # IBU raisonnable (0-150)
                    if 0 <= ibu <= 150:
                        metadata['ibu'] = match.group(1)

        return metadata

    def _extract_categories(self, soup: BeautifulSoup) -> Dict:
        """Extrait producteur, style depuis les catégories/liens"""
        data = {
            'producer': None,
            'style': None,
            'sub_style': None
        }

        # Cherche dans les liens de catégorie
        for a in soup.find_all('a', href=True):
            href = a.get('href', '').lower()
            text = a.get_text(strip=True)

            if not text or len(text) > 50:  # Ignore texte trop long
                continue

            # Producteur/Brasserie
            if not data['producer']:
                if any(x in href for x in ['brand', 'vendor', 'brasserie', 'brewery', 'producer', 'producteur']):
                    # Ignore les termes génériques
                    if text.lower() not in ['bière', 'beer', 'produits', 'products']:
                        data['producer'] = text

            # Style
            if any(x in href for x in ['style', 'category', 'type']):
                if text.lower() not in ['bière', 'beer', 'produits', 'products', 'boutique', 'shop']:
                    if not data['style']:
                        data['style'] = text
                    elif data['style'] and data['style'].lower() not in text.lower():
                        data['sub_style'] = text

        # Aussi chercher dans meta
        brand_meta = soup.find('meta', attrs={'itemprop': 'brand'})
        if brand_meta and brand_meta.get('content') and not data['producer']:
            data['producer'] = brand_meta['content']

        return data

    # ============================================================================
    # CRAWL PRINCIPAL
    # ============================================================================

    def save_progress(self, filename: str):
        """Sauvegarde progressive"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.beers, f, ensure_ascii=False, indent=2)

    def crawl(self, output_filename: str = 'beers_universal.json'):
        """Crawl complet du site"""
        print("="*80)
        print(f"🍺 UNIVERSAL BEER CRAWLER")
        print(f"   Site: {self.base_url}")
        print("="*80)

        try:
            # 1. Découverte des produits
            product_links = self.discover_product_links()

            if not product_links:
                print("\n❌ Aucun produit trouvé!")
                return []

            # 2. Extraction des données
            print(f"\n📸 Extraction des données de {len(product_links)} produits...\n")

            for i, url in enumerate(product_links, 1):
                slug = url.split('/')[-1] if url.split('/')[-1] else url.split('/')[-2]
                print(f"[{i}/{len(product_links)}] {slug}")

                beer = self.extract_beer_data(url)

                if beer:
                    self.beers.append(beer)

                    # Affiche résumé
                    print(f"  ✓ {beer.get('name', 'N/A')}")
                    if beer.get('price'):
                        print(f"  💰 {beer['price']}")
                    if beer.get('alcohol'):
                        print(f"  🍺 {beer['alcohol']}", end='')
                        if beer.get('volume'):
                            print(f" - {beer['volume']}", end='')
                        print()
                    if beer.get('photo_url'):
                        print(f"  📸 Photo disponible")

                    # Sauvegarde progressive
                    self.save_progress(output_filename)
                    print(f"  💾 Sauvegardé ({len(self.beers)} bières)\n")

                time.sleep(1)  # Pause entre requêtes

            # 3. Statistiques finales
            print("\n" + "="*80)
            print("🎉 CRAWLING TERMINÉ!")
            print("="*80)
            print(f"  Total bières: {len(self.beers)}")
            print(f"  Avec photo: {sum(1 for b in self.beers if b.get('photo_url'))}")
            print(f"  Avec alcool: {sum(1 for b in self.beers if b.get('alcohol'))}")
            print(f"  Avec prix: {sum(1 for b in self.beers if b.get('price'))}")
            print(f"\n📁 Fichier: {output_filename}")

            # Sauvegarde config pour réutilisation
            with open('crawler_config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"⚙️  Config: crawler_config.json")

        finally:
            self.driver.quit()

        return self.beers


# ================================================================================
# UTILISATION
# ================================================================================

if __name__ == "__main__":
    import sys

    # Parse arguments
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    args = [arg for arg in sys.argv[1:] if not arg.startswith('-')]

    if len(args) < 1:
        print("="*80)
        print("🍺 UNIVERSAL BEER CRAWLER")
        print("="*80)
        print("\nUsage: python universal-crawler.py <URL> [output_file] [--verbose]")
        print("\nExemples:")
        print("  python universal-crawler.py https://dieuduciel.com")
        print("  python universal-crawler.py https://microbrasserie.com beers_custom.json")
        print("  python universal-crawler.py https://dieuduciel.com --verbose")
        print("\nOptions:")
        print("  --verbose, -v  Affiche les détails de debug")
        print("\nCe crawler s'adapte automatiquement à n'importe quel site de brasserie!")
        print("="*80)
        sys.exit(1)

    base_url = args[0]
    output_file = args[1] if len(args) > 1 else 'beers_universal.json'

    # Lance le crawler
    crawler = UniversalBeerCrawler(base_url, headless=True, verbose=verbose)
    beers = crawler.crawl(output_file)

    if beers:
        print("\n📋 Exemple de bière extraite:")
        print(json.dumps(beers[0], indent=2, ensure_ascii=False))
