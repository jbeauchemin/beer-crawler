from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import json
import re

class MaSoifCrawler:
    def __init__(self, headless=True):
        self.base_url = "https://masoif.com"
        self.category_url = "https://masoif.com/categorie/ma-soif"
        self.beers = []
        
        # Configuration Chrome
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
    
    def get_all_product_links(self):
        """Récupère tous les liens en parcourant toutes les pages de pagination"""
        print("📋 Récupération de tous les produits...\n")
        
        product_links = set()
        page = 1
        max_pages = 100  # Limite de sécurité
        
        while page <= max_pages:
            if page == 1:
                url = self.category_url + "/"
            else:
                url = f"{self.category_url}/page/{page}/"
            
            print(f"  Page {page}: Chargement...")
            
            try:
                self.driver.get(url)
                time.sleep(3)  # Attendre le chargement
                
                # Parser le HTML
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Trouver les liens de produits sur cette page
                links_on_page = []
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    # Chercher les URLs de produits
                    if '/produit/' in href:
                        if href.startswith('/'):
                            href = self.base_url + href
                        href = href.split('?')[0]
                        if href not in product_links:
                            product_links.add(href)
                            links_on_page.append(href)
                
                if not links_on_page:
                    print(f"  ✓ Aucun nouveau produit - Fin à la page {page-1}\n")
                    break
                
                print(f"    → {len(links_on_page)} nouveaux produits trouvés")
                print(f"    → Total: {len(product_links)} produits uniques\n")
                
                page += 1
                
            except Exception as e:
                print(f"  ✗ Erreur: {e}")
                break
        
        print(f"✓ {len(product_links)} produits au total!\n")
        
        # Sauvegarder pour debug
        with open('product_links_masoif.txt', 'w') as f:
            for link in sorted(product_links):
                f.write(link + '\n')
        
        return list(product_links)
    
    def extract_beer_data(self, product_url):
        """Extrait toutes les données d'une bière"""
        try:
            self.driver.get(product_url)
            time.sleep(2)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            beer = {
                'url': product_url,
                'name': None,
                'price': None,
                'producer': None,
                'style': None,
                'sub_style': None,
                'volume': None,
                'alcohol': None,
                'ibu': None,
                'region': None,
                'description': None,
                'photo_url': None,
                'availability': None
            }
            
            # Nom du produit
            title = soup.find('h1', class_='product_title')
            if title:
                beer['name'] = title.get_text(strip=True)
            
            # Prix - chercher dans la balise avec class="price"
            price_elem = soup.find('p', class_='price')
            if price_elem:
                price_amount = price_elem.find('span', class_='woocommerce-Price-amount')
                if price_amount:
                    beer['price'] = price_amount.get_text(strip=True)
            
            # Attributs principaux (brasserie, alcool, volume) - dans <ul class="attributs-biere">
            attributs_biere = soup.find('ul', class_='attributs-biere')
            if attributs_biere:
                items = attributs_biere.find_all('li')
                for item in items:
                    value = item.get_text(strip=True)
                    
                    # Brasserie (lien)
                    link = item.find('a')
                    if link and '/brasserie/' in link.get('href', ''):
                        beer['producer'] = link.get_text(strip=True)
                    # Alcool (contient %)
                    elif '%' in value:
                        beer['alcohol'] = value
                    # Volume (contient ml)
                    elif 'ml' in value.lower():
                        beer['volume'] = value
            
            # Description - dans la div avec class="single-product-desc"
            desc_elem = soup.find('div', class_='single-product-desc')
            if desc_elem:
                # Chercher d'abord un <p>
                desc_p = desc_elem.find('p')
                if desc_p:
                    beer['description'] = desc_p.get_text(strip=True)
                else:
                    # Sinon, prendre tout le texte de la div (pour les descriptions en <div dir="auto">)
                    shortcode_div = desc_elem.find('div', class_='elementor-shortcode')
                    if shortcode_div:
                        # Récupérer tous les textes et joindre avec des espaces
                        desc_texts = []
                        for div in shortcode_div.find_all('div', dir='auto'):
                            text = div.get_text(strip=True)
                            if text and text != '•':  # Ignorer les séparateurs
                                desc_texts.append(text)
                        if desc_texts:
                            beer['description'] = ' '.join(desc_texts)
            
            # Fiche produit détaillée - dans <ul class="fiche-produit">
            fiche_produit = soup.find('ul', class_='fiche-produit')
            if fiche_produit:
                items = fiche_produit.find_all('li')
                for item in items:
                    label_elem = item.find('span', class_='attribute-label')
                    value_elem = item.find('span', class_='attribute-value')
                    
                    if label_elem and value_elem:
                        label = label_elem.get_text(strip=True).lower()
                        
                        # Région
                        if 'région' in label or 'region' in label:
                            link = value_elem.find('a')
                            if link:
                                beer['region'] = link.get_text(strip=True)
                            else:
                                beer['region'] = value_elem.get_text(strip=True)
                        
                        # IBU
                        elif 'ibu' in label:
                            beer['ibu'] = value_elem.get_text(strip=True)
                        
                        # Profil (style)
                        elif 'profil' in label or 'style' in label:
                            link = value_elem.find('a')
                            if link:
                                beer['style'] = link.get_text(strip=True)
                            else:
                                beer['style'] = value_elem.get_text(strip=True)
            
            # Disponibilité
            stock_elem = soup.find('span', class_='stock')
            if stock_elem:
                beer['availability'] = stock_elem.get_text(strip=True)
            
            # Photo principale - chercher dans woocommerce-product-gallery__image
            gallery = soup.find('div', class_='woocommerce-product-gallery__image')
            if gallery:
                img = gallery.find('img', class_='wp-post-image')
                if img:
                    # Prendre data-large_image en priorité, sinon src
                    photo_url = img.get('data-large_image') or img.get('src')
                    if photo_url:
                        # Enlever les paramètres de redimensionnement
                        photo_url = photo_url.split('?')[0]
                        if photo_url.startswith('//'):
                            photo_url = 'https:' + photo_url
                        beer['photo_url'] = photo_url
            
            # Si pas trouvé, chercher Open Graph image
            if not beer['photo_url']:
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    photo_url = og_image['content'].split('?')[0]
                    if photo_url.startswith('//'):
                        photo_url = 'https:' + photo_url
                    beer['photo_url'] = photo_url
            
            return beer
            
        except Exception as e:
            print(f"  ✗ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_progress(self, filename='beers_masoif.json'):
        """Sauvegarde le progrès actuel en JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.beers, f, ensure_ascii=False, indent=2)
    
    def crawl(self, json_filename='beers_masoif.json'):
        """Crawl principal avec sauvegarde progressive"""
        print("🍺 Début du crawling de MaSoif.com\n")
        
        try:
            # 1. Récupérer tous les liens de toutes les pages
            product_links = self.get_all_product_links()
            
            # 2. Crawler chaque produit
            print("📸 Extraction des données de chaque bière...\n")
            for i, url in enumerate(product_links, 1):
                product_name = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
                print(f"[{i}/{len(product_links)}] {product_name}")
                
                beer = self.extract_beer_data(url)
                
                if beer and beer['name']:
                    self.beers.append(beer)
                    print(f"  ✓ {beer['name']}")
                    if beer.get('producer'):
                        print(f"  🏭 {beer['producer']}")
                    if beer.get('alcohol'):
                        print(f"  🍺 {beer['alcohol']}")
                    if beer['photo_url']:
                        print(f"  📸 Photo trouvée")
                    
                    # Sauvegarder après chaque bière
                    self.save_progress(json_filename)
                    print(f"  💾 Sauvegardé ({len(self.beers)} bières)\n")
                else:
                    print(f"  ⚠️ Données incomplètes, ignoré\n")
                
                time.sleep(1)
            
            print(f"\n🎉 Crawling terminé!")
            print(f"  Total bières: {len(self.beers)}")
            beers_with_photos = sum(1 for b in self.beers if b.get('photo_url'))
            print(f"  Bières avec photo: {beers_with_photos}")
            beers_with_producer = sum(1 for b in self.beers if b.get('producer'))
            print(f"  Bières avec brasserie: {beers_with_producer}")
            
        finally:
            self.driver.quit()
        
        return self.beers
    
    def save_to_json(self, filename='beers_masoif.json'):
        """Sauvegarde finale en JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.beers, f, ensure_ascii=False, indent=2)
        print(f"💾 Sauvegarde finale dans {filename}")


# ===== UTILISATION =====
if __name__ == "__main__":
    # headless=True pour mode silencieux, False pour voir le navigateur
    crawler = MaSoifCrawler(headless=True)
    
    # Lancer le crawling (sauvegarde automatique après chaque bière)
    beers = crawler.crawl('beers_masoif.json')
    
    print("\n✅ Terminé! Le fichier beers_masoif.json contient toutes les bières.")
    
    # Afficher un exemple
    if beers:
        print("\n📋 Exemple de bière:")
        print(json.dumps(beers[0], indent=2, ensure_ascii=False))