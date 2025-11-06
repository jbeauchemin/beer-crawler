#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Site Analyzer Lite - Analyse de sites de microbrasserie sans Selenium
Utilise requests + BeautifulSoup pour l'analyse initiale
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from collections import Counter
from urllib.parse import urljoin, urlparse, parse_qs
import time


class SiteAnalyzerLite:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        self.analysis = {
            'base_url': base_url,
            'product_links': [],
            'listing_pages': [],
            'url_patterns': Counter(),
            'platform': None,
            'structure': {},
            'sample_products': []
        }

    def fetch_page(self, url, timeout=10):
        """Récupère une page web"""
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"❌ Erreur lors du chargement de {url}: {e}")
            return None

    def detect_platform(self, soup):
        """Détecte la plateforme (Shopify, WordPress, WooCommerce, etc.)"""
        html = str(soup)

        if 'shopify' in html.lower() or 'cdn.shopify.com' in html:
            return 'Shopify'
        elif 'woocommerce' in html.lower():
            return 'WooCommerce'
        elif 'wp-content' in html.lower() or 'wordpress' in html.lower():
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
        # Ne pas prendre les pages de catégorie/collection avec paramètres
        if re.search(r'[?&](page|sort|filter|limit)=', url, re.IGNORECASE):
            return False

        # Patterns de produits
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
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return False

    def normalize_url(self, href, base_url=None):
        """Normalise une URL"""
        if not href:
            return None

        # URL absolue
        if href.startswith('http'):
            url = href
        # URL relative
        elif href.startswith('/'):
            url = self.base_url + href
        else:
            url = urljoin(base_url or self.base_url, href)

        # Nettoie
        url = url.split('#')[0]  # Retire les ancres

        # Ne nettoie PAS les paramètres pour les listings (pagination, etc.)
        # On le fera seulement pour les produits
        if self.is_product_url(url):
            url = url.split('?')[0]

        return url.rstrip('/')

    def analyze_homepage(self):
        """Analyse la page d'accueil"""
        print(f"\n🔍 Analyse de la page d'accueil: {self.base_url}\n")

        soup = self.fetch_page(self.base_url)
        if not soup:
            return []

        # Détecte la plateforme
        self.analysis['platform'] = self.detect_platform(soup)
        print(f"📦 Plateforme détectée: {self.analysis['platform']}\n")

        # Trouve tous les liens
        all_links = set()
        for a in soup.find_all('a', href=True):
            url = self.normalize_url(a['href'])
            if url and self.domain in url:
                all_links.add(url)

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

        self.analysis['product_links'] = sorted(set(product_links))
        self.analysis['listing_pages'] = sorted(set(listing_links))

        print(f"🍺 Liens de produits trouvés: {len(self.analysis['product_links'])}")
        if self.analysis['product_links'][:5]:
            print("   Exemples:")
            for link in self.analysis['product_links'][:5]:
                print(f"   - {link}")

        print(f"\n📋 Pages de listing trouvées: {len(self.analysis['listing_pages'])}")
        if self.analysis['listing_pages']:
            print("   Pages:")
            for link in self.analysis['listing_pages']:
                print(f"   - {link}")

        print(f"\n📊 Patterns d'URL détectés:")
        for pattern, count in self.analysis['url_patterns'].most_common():
            print(f"   {pattern}: {count} liens")

        return self.analysis['listing_pages']

    def analyze_listing_page(self, url):
        """Analyse une page de liste de produits"""
        print(f"\n\n🔍 Analyse de la page de listing: {url}\n")

        soup = self.fetch_page(url)
        if not soup:
            return []

        # Trouve les liens de produits
        product_links = set()

        for a in soup.find_all('a', href=True):
            product_url = self.normalize_url(a['href'])
            if product_url and self.domain in product_url and self.is_product_url(product_url):
                product_links.add(product_url)

        print(f"🍺 Produits trouvés: {len(product_links)}")
        if product_links:
            print("   Exemples:")
            for link in list(product_links)[:5]:
                print(f"   - {link}")

        # Détecte la pagination
        pagination_links = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a.get('href', '')

            # Cherche les liens de pagination
            if any(x in text.lower() for x in ['next', 'suivant', 'prochain', '›', '»']):
                pag_url = self.normalize_url(href)
                if pag_url:
                    pagination_links.append(('next', pag_url))

            # Numéros de page
            if text.isdigit() and int(text) > 1:
                pag_url = self.normalize_url(href)
                if pag_url:
                    pagination_links.append(('page', pag_url))

        if pagination_links:
            print(f"\n📄 Pagination détectée: {len(pagination_links)} liens")
            for ptype, link in list(set(pagination_links))[:3]:
                print(f"   [{ptype}] {link}")

        return list(product_links)

    def analyze_product_page(self, url):
        """Analyse détaillée d'une page produit"""
        print(f"\n\n🔍 Analyse de la page produit: {url}\n")

        soup = self.fetch_page(url)
        if not soup:
            return {}

        info = {
            'url': url,
            'selectors_found': {}
        }

        # 1. Nom
        print("📝 Recherche du NOM:")
        h1 = soup.find('h1')
        if h1:
            info['name'] = h1.get_text(strip=True)
            info['selectors_found']['name'] = 'h1'
            print(f"   ✓ h1: {info['name']}")

        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            print(f"   ✓ og:title: {og_title['content']}")
            if 'name' not in info:
                info['name'] = og_title['content']
                info['selectors_found']['name'] = 'og:title'

        # 2. Prix
        print("\n💰 Recherche du PRIX:")
        price_selectors = [
            ('class~=price', soup.find_all(class_=re.compile(r'price', re.I))),
            ('data-price', soup.find_all(attrs={'data-price': True})),
            ('itemprop=price', soup.find_all(attrs={'itemprop': 'price'})),
        ]

        for selector_name, elements in price_selectors:
            for elem in elements[:2]:
                text = elem.get_text(strip=True)
                if text and any(c in text for c in ['$', 'CAD', '€', ',00', '.00']):
                    print(f"   ✓ {selector_name}: {text}")
                    if 'price' not in info:
                        info['price'] = text
                        info['selectors_found']['price'] = selector_name
                        break

        # 3. Description
        print("\n📄 Recherche de la DESCRIPTION:")
        desc_selectors = [
            ('class~=description', soup.find_all(class_=re.compile(r'description', re.I))),
            ('itemprop=description', soup.find_all(attrs={'itemprop': 'description'})),
            ('id~=description', soup.find_all(id=re.compile(r'description', re.I))),
        ]

        for selector_name, elements in desc_selectors:
            for elem in elements[:1]:
                text = elem.get_text(strip=True)
                if text and len(text) > 20:
                    preview = text[:100] + '...' if len(text) > 100 else text
                    print(f"   ✓ {selector_name}: {preview}")
                    if 'description' not in info:
                        info['description'] = text
                        info['selectors_found']['description'] = selector_name
                        break

        # 4. Image
        print("\n📸 Recherche de l'IMAGE:")
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            info['photo_url'] = og_image['content']
            info['selectors_found']['photo'] = 'og:image'
            print(f"   ✓ og:image: {og_image['content']}")

        # 5. Métadonnées bière (%, ml, IBU, etc.)
        print("\n🍺 Recherche des MÉTADONNÉES BIÈRE:")

        # Analyse tout le texte
        for elem in soup.find_all(['li', 'div', 'p', 'span', 'td', 'th']):
            text = elem.get_text(' ', strip=True)

            # Alcool (%)
            if 'alcohol' not in info and re.search(r'\d+\.?\d*\s*%', text):
                match = re.search(r'(\d+\.?\d*)\s*%', text)
                if match:
                    alc = float(match.group(1))
                    # Valide que c'est bien de l'alcool (entre 0% et 20%)
                    if 0 <= alc <= 20:
                        print(f"   ✓ Alcool: {match.group(1)}% (dans {elem.name})")
                        info['alcohol'] = match.group(1) + '%'

            # Volume (ml)
            if 'volume' not in info and re.search(r'\d{2,5}\s*ml', text, re.I):
                match = re.search(r'(\d{2,5})\s*ml', text, re.I)
                if match:
                    vol = int(match.group(1))
                    # Valide que c'est un volume raisonnable
                    if 100 <= vol <= 5000:
                        print(f"   ✓ Volume: {match.group(1)}ml (dans {elem.name})")
                        info['volume'] = match.group(1) + 'ml'

            # IBU
            if 'ibu' not in info and re.search(r'\d+\s*ibu', text, re.I):
                match = re.search(r'(\d+)\s*ibu', text, re.I)
                if match:
                    print(f"   ✓ IBU: {match.group(1)} (dans {elem.name})")
                    info['ibu'] = match.group(1)

        # 6. Style / Catégorie
        print("\n🎨 Recherche du STYLE:")
        # Cherche dans les métadonnées
        for a in soup.find_all('a', href=True):
            href = a.get('href', '').lower()
            text = a.get_text(strip=True)

            # Si le lien contient 'style', 'category', etc.
            if any(x in href for x in ['style', 'category', 'categorie', 'type']) and text:
                # Ne pas prendre les liens génériques
                if text.lower() not in ['bière', 'beer', 'produits', 'products', 'boutique', 'shop']:
                    print(f"   ✓ Style potentiel: {text} (lien: {href})")
                    if 'style' not in info:
                        info['style'] = text
                        info['selectors_found']['style'] = 'category_link'

        # 7. Producteur
        print("\n🏭 Recherche du PRODUCTEUR:")
        producer_selectors = [
            ('meta brand', soup.find('meta', attrs={'itemprop': 'brand'})),
            ('class~=brand', soup.find(class_=re.compile(r'brand', re.I))),
            ('class~=vendor', soup.find(class_=re.compile(r'vendor', re.I))),
            ('class~=producer', soup.find(class_=re.compile(r'producer', re.I))),
        ]

        for selector_name, elem in producer_selectors:
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

        # Résumé
        print("\n" + "="*60)
        print("📊 RÉSUMÉ DES DONNÉES EXTRAITES:")
        print("="*60)
        for key, value in info.items():
            if key not in ['url', 'selectors_found']:
                selector = info['selectors_found'].get(key, '?')
                val_str = str(value)[:80]
                print(f"{key:15} [{selector:20}]: {val_str}")

        return info

    def run_full_analysis(self):
        """Analyse complète du site"""
        print("="*80)
        print(f"🍺 ANALYSE COMPLÈTE DU SITE: {self.base_url}")
        print("="*80)

        # 1. Homepage
        listing_pages = self.analyze_homepage()

        # 2. Première page de listing
        if listing_pages:
            first_listing = listing_pages[0]
            product_links = self.analyze_listing_page(first_listing)

            # Combine avec les produits de la homepage
            all_products = set(self.analysis['product_links']) | set(product_links)
            self.analysis['product_links'] = sorted(all_products)

        # 3. Analyse détaillée de 3 produits
        if self.analysis['product_links']:
            print(f"\n\n{'='*80}")
            print(f"🔬 ANALYSE DÉTAILLÉE DE 3 PRODUITS")
            print("="*80)

            sample_products = self.analysis['product_links'][:3]

            for product_url in sample_products:
                product_info = self.analyze_product_page(product_url)
                self.analysis['sample_products'].append(product_info)
                time.sleep(1)  # Pause entre les requêtes

        # 4. Sauvegarde
        output_file = 'site_analysis.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            # Convertir les Counter en dict pour JSON
            analysis_copy = self.analysis.copy()
            analysis_copy['url_patterns'] = dict(analysis_copy['url_patterns'])
            json.dump(analysis_copy, f, ensure_ascii=False, indent=2)

        print(f"\n\n{'='*80}")
        print(f"✅ ANALYSE TERMINÉE")
        print("="*80)
        print(f"📁 Résultats sauvegardés dans: {output_file}")
        print(f"\n📊 Statistiques:")
        print(f"   - Plateforme: {self.analysis['platform']}")
        print(f"   - Pages de listing: {len(self.analysis['listing_pages'])}")
        print(f"   - Produits trouvés: {len(self.analysis['product_links'])}")
        print(f"   - Produits analysés: {len(self.analysis['sample_products'])}")

        return self.analysis


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python site-analyzer-lite.py <URL>")
        print("Exemple: python site-analyzer-lite.py https://dieuduciel.com")
        sys.exit(1)

    url = sys.argv[1]
    analyzer = SiteAnalyzerLite(url)
    analyzer.run_full_analysis()
