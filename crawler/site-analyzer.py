#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Site Analyzer - Analyse automatique de sites de microbrasserie
Trouve les patterns pour crawler n'importe quel site
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from bs4 import BeautifulSoup
import time
import json
import re
from collections import Counter
from urllib.parse import urljoin, urlparse


class SiteAnalyzer:
    def __init__(self, base_url, headless=True):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc

        # Configuration Chrome
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        # Utilise webdriver-manager pour installer Chrome automatiquement
        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

        self.analysis = {
            'base_url': base_url,
            'product_links': [],
            'listing_pages': [],
            'url_patterns': Counter(),
            'platform': None,
            'structure': {}
        }

    def detect_platform(self, soup):
        """Détecte la plateforme (Shopify, WordPress, WooCommerce, etc.)"""
        html = str(soup)

        if 'shopify' in html.lower() or 'cdn.shopify.com' in html:
            return 'Shopify'
        elif 'woocommerce' in html.lower() or 'wp-content' in html:
            return 'WooCommerce'
        elif 'wordpress' in html.lower():
            return 'WordPress'
        elif 'squarespace' in html.lower():
            return 'Squarespace'
        else:
            return 'Custom/Unknown'

    def find_product_patterns(self, url):
        """Patterns communs pour les produits de bière"""
        common_patterns = [
            r'/products?/',
            r'/produits?/',
            r'/biere[s]?/',
            r'/beer[s]?/',
            r'/boutique/',
            r'/shop/',
            r'/collections?/',
            r'/catalogue/',
        ]

        for pattern in common_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return pattern
        return None

    def is_product_url(self, url):
        """Détermine si une URL est un produit"""
        # Ne pas prendre les pages de catégorie/collection
        if re.search(r'(page|collections?|categories?|tags?)[/=]', url, re.IGNORECASE):
            return False

        # Cherche les patterns de produits
        product_patterns = [
            r'/products?/[^/]+/?$',
            r'/produits?/[^/]+/?$',
            r'/biere[s]?/[^/]+/?$',
            r'/beer[s]?/[^/]+/?$',
        ]

        for pattern in product_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return False

    def is_listing_url(self, url):
        """Détermine si une URL est une page de liste"""
        listing_patterns = [
            r'/products?/?$',
            r'/produits?/?$',
            r'/biere[s]?/?$',
            r'/beer[s]?/?$',
            r'/boutique/?$',
            r'/shop/?$',
            r'/collections?/',
            r'/catalogue/?$',
        ]

        for pattern in listing_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return False

    def analyze_homepage(self):
        """Analyse la page d'accueil pour trouver les liens"""
        print(f"\n🔍 Analyse de la page d'accueil: {self.base_url}\n")

        try:
            self.driver.get(self.base_url)
            time.sleep(3)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Détecte la plateforme
            self.analysis['platform'] = self.detect_platform(soup)
            print(f"📦 Plateforme détectée: {self.analysis['platform']}\n")

            # Trouve tous les liens
            all_links = set()
            for a in soup.find_all('a', href=True):
                href = a['href']

                # Normalise l'URL
                if href.startswith('/'):
                    href = self.base_url + href
                elif not href.startswith('http'):
                    href = urljoin(self.base_url, href)

                # Garde seulement les liens du même domaine
                if self.domain in href:
                    # Nettoie les paramètres
                    href = href.split('?')[0].split('#')[0].rstrip('/')
                    all_links.add(href)

            print(f"🔗 Total de liens trouvés: {len(all_links)}\n")

            # Catégorise les liens
            product_links = []
            listing_links = []

            for link in all_links:
                if self.is_product_url(link):
                    product_links.append(link)
                    pattern = self.find_product_patterns(link)
                    if pattern:
                        self.analysis['url_patterns'][pattern] += 1

                elif self.is_listing_url(link):
                    listing_links.append(link)

            self.analysis['product_links'] = sorted(product_links)
            self.analysis['listing_pages'] = sorted(listing_links)

            print(f"🍺 Liens de produits trouvés: {len(product_links)}")
            if product_links[:5]:
                print("   Exemples:")
                for link in product_links[:5]:
                    print(f"   - {link}")

            print(f"\n📋 Pages de listing trouvées: {len(listing_links)}")
            if listing_links:
                print("   Pages:")
                for link in listing_links:
                    print(f"   - {link}")

            print(f"\n📊 Patterns d'URL détectés:")
            for pattern, count in self.analysis['url_patterns'].most_common():
                print(f"   {pattern}: {count} liens")

            return listing_links

        except Exception as e:
            print(f"❌ Erreur lors de l'analyse: {e}")
            import traceback
            traceback.print_exc()
            return []

    def analyze_listing_page(self, url):
        """Analyse une page de liste de produits"""
        print(f"\n\n🔍 Analyse de la page de listing: {url}\n")

        try:
            self.driver.get(url)
            time.sleep(3)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Trouve les liens de produits sur cette page
            product_links = set()

            for a in soup.find_all('a', href=True):
                href = a['href']

                # Normalise l'URL
                if href.startswith('/'):
                    href = self.base_url + href
                elif not href.startswith('http'):
                    href = urljoin(self.base_url, href)

                # Vérifie si c'est un produit
                if self.domain in href and self.is_product_url(href):
                    href = href.split('?')[0].split('#')[0].rstrip('/')
                    product_links.add(href)

            print(f"🍺 Produits trouvés sur cette page: {len(product_links)}")
            if product_links:
                print("   Exemples:")
                for link in list(product_links)[:5]:
                    print(f"   - {link}")

            # Détecte la pagination
            pagination_links = []
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True)
                href = a['href']

                # Cherche les liens de pagination
                if any(x in text.lower() for x in ['next', 'suivant', 'prochain', '›', '»']):
                    if href.startswith('/'):
                        href = self.base_url + href
                    pagination_links.append(('next', href))

                # Cherche les numéros de page
                if text.isdigit() and int(text) > 1:
                    if href.startswith('/'):
                        href = self.base_url + href
                    pagination_links.append(('page', href))

            if pagination_links:
                print(f"\n📄 Pagination détectée: {len(pagination_links)} liens")
                for ptype, link in pagination_links[:3]:
                    print(f"   [{ptype}] {link}")

            return list(product_links)

        except Exception as e:
            print(f"❌ Erreur lors de l'analyse: {e}")
            import traceback
            traceback.print_exc()
            return []

    def analyze_product_page(self, url):
        """Analyse une page de détail produit"""
        print(f"\n\n🔍 Analyse de la page produit: {url}\n")

        try:
            self.driver.get(url)
            time.sleep(2)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            info = {
                'url': url,
                'selectors_found': {}
            }

            # 1. Nom (h1, title, og:title)
            print("📝 Recherche du NOM:")
            h1 = soup.find('h1')
            if h1:
                info['name'] = h1.get_text(strip=True)
                info['selectors_found']['name'] = 'h1'
                print(f"   ✓ h1: {info['name']}")

            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                print(f"   ✓ og:title: {og_title['content']}")

            # 2. Prix
            print("\n💰 Recherche du PRIX:")
            price_selectors = [
                ('class~=price', soup.find_all(class_=re.compile(r'price', re.I))),
                ('data-price', soup.find_all(attrs={'data-price': True})),
                ('itemprop=price', soup.find_all(attrs={'itemprop': 'price'})),
            ]

            for selector_name, elements in price_selectors:
                for elem in elements[:2]:  # Max 2 exemples par sélecteur
                    text = elem.get_text(strip=True)
                    if text and any(c in text for c in ['$', 'CAD', '€']):
                        print(f"   ✓ {selector_name}: {text}")
                        if 'price' not in info:
                            info['price'] = text
                            info['selectors_found']['price'] = selector_name

            # 3. Description
            print("\n📄 Recherche de la DESCRIPTION:")
            desc_selectors = [
                ('class~=description', soup.find_all(class_=re.compile(r'description', re.I))),
                ('itemprop=description', soup.find_all(attrs={'itemprop': 'description'})),
                ('id~=description', soup.find_all(id=re.compile(r'description', re.I))),
            ]

            for selector_name, elements in desc_selectors:
                for elem in elements[:1]:  # 1 exemple
                    text = elem.get_text(strip=True)
                    if text and len(text) > 20:
                        preview = text[:100] + '...' if len(text) > 100 else text
                        print(f"   ✓ {selector_name}: {preview}")
                        if 'description' not in info:
                            info['description'] = text
                            info['selectors_found']['description'] = selector_name

            # 4. Image
            print("\n📸 Recherche de l'IMAGE:")
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                info['photo_url'] = og_image['content']
                info['selectors_found']['photo'] = 'og:image'
                print(f"   ✓ og:image: {og_image['content']}")

            # 5. Métadonnées spécifiques bière
            print("\n🍺 Recherche des MÉTADONNÉES BIÈRE:")

            # Cherche alcool (%)
            for elem in soup.find_all(['li', 'div', 'p', 'span']):
                text = elem.get_text(strip=True)

                # Alcool
                if re.search(r'\d+\.?\d*\s*%', text):
                    match = re.search(r'(\d+\.?\d*)\s*%', text)
                    if match:
                        print(f"   ✓ Alcool trouvé: {match.group(1)}% dans {elem.name}.{elem.get('class', '')}")
                        if 'alcohol' not in info:
                            info['alcohol'] = match.group(1) + '%'

                # Volume
                if re.search(r'\d+\s*ml', text, re.I):
                    match = re.search(r'(\d+)\s*ml', text, re.I)
                    if match:
                        print(f"   ✓ Volume trouvé: {match.group(1)}ml dans {elem.name}.{elem.get('class', '')}")
                        if 'volume' not in info:
                            info['volume'] = match.group(1) + 'ml'

                # IBU
                if re.search(r'ibu', text, re.I):
                    match = re.search(r'(\d+)\s*ibu', text, re.I)
                    if match:
                        print(f"   ✓ IBU trouvé: {match.group(1)} dans {elem.name}.{elem.get('class', '')}")
                        if 'ibu' not in info:
                            info['ibu'] = match.group(1)

            # 6. Producteur / Brasserie
            print("\n🏭 Recherche du PRODUCTEUR:")
            producer_patterns = [
                ('meta brand', soup.find('meta', attrs={'itemprop': 'brand'})),
                ('class~=brand', soup.find(class_=re.compile(r'brand', re.I))),
                ('class~=vendor', soup.find(class_=re.compile(r'vendor', re.I))),
            ]

            for selector_name, elem in producer_patterns:
                if elem:
                    if elem.name == 'meta' and elem.get('content'):
                        print(f"   ✓ {selector_name}: {elem['content']}")
                        if 'producer' not in info:
                            info['producer'] = elem['content']
                            info['selectors_found']['producer'] = selector_name
                    else:
                        text = elem.get_text(strip=True)
                        if text:
                            print(f"   ✓ {selector_name}: {text}")
                            if 'producer' not in info:
                                info['producer'] = text
                                info['selectors_found']['producer'] = selector_name

            print("\n" + "="*60)
            print("📊 RÉSUMÉ DES DONNÉES EXTRAITES:")
            print("="*60)
            for key, value in info.items():
                if key not in ['url', 'selectors_found']:
                    selector = info['selectors_found'].get(key, '?')
                    print(f"{key:15} [{selector:20}]: {str(value)[:80]}")

            return info

        except Exception as e:
            print(f"❌ Erreur lors de l'analyse: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def run_full_analysis(self):
        """Analyse complète du site"""
        print("="*80)
        print(f"🍺 ANALYSE COMPLÈTE DU SITE: {self.base_url}")
        print("="*80)

        try:
            # 1. Analyse homepage
            listing_pages = self.analyze_homepage()

            # 2. Si on a trouvé des pages de listing, en analyser une
            if listing_pages:
                first_listing = listing_pages[0]
                product_links = self.analyze_listing_page(first_listing)

                # Combine avec les produits de la homepage
                all_products = set(self.analysis['product_links']) | set(product_links)
                self.analysis['product_links'] = sorted(all_products)

            # 3. Analyser quelques pages produits
            if self.analysis['product_links']:
                print(f"\n\n{'='*80}")
                print(f"🔬 ANALYSE DÉTAILLÉE DE 3 PRODUITS")
                print("="*80)

                sample_products = self.analysis['product_links'][:3]
                product_analyses = []

                for product_url in sample_products:
                    product_info = self.analyze_product_page(product_url)
                    product_analyses.append(product_info)

                self.analysis['sample_products'] = product_analyses

            # 4. Sauvegarde l'analyse
            output_file = 'site_analysis.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.analysis, f, ensure_ascii=False, indent=2)

            print(f"\n\n{'='*80}")
            print(f"✅ ANALYSE TERMINÉE")
            print("="*80)
            print(f"📁 Résultats sauvegardés dans: {output_file}")
            print(f"\n📊 Statistiques:")
            print(f"   - Plateforme: {self.analysis['platform']}")
            print(f"   - Pages de listing: {len(self.analysis['listing_pages'])}")
            print(f"   - Produits trouvés: {len(self.analysis['product_links'])}")
            print(f"   - Produits analysés: {len(self.analysis.get('sample_products', []))}")

        finally:
            self.driver.quit()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python site-analyzer.py <URL>")
        print("Exemple: python site-analyzer.py https://dieuduciel.com")
        sys.exit(1)

    url = sys.argv[1]
    analyzer = SiteAnalyzer(url, headless=True)
    analyzer.run_full_analysis()
