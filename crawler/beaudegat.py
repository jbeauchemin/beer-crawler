from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import json
import re

class BeaudegatCrawler:
    def __init__(self, headless=True):
        self.base_url = "https://beaudegat.ca"
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
        """Récupère tous les liens en parcourant toutes les pages"""
        print("📋 Récupération de tous les produits...\n")
        
        product_links = set()
        page = 1
        max_pages = 200  # Limite de sécurité
        
        while page <= max_pages:
            url = f"{self.base_url}/collections/biere?page={page}"
            print(f"  Page {page}: Chargement...")
            
            try:
                self.driver.get(url)
                time.sleep(2)
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Trouver les liens de produits (classe "full-unstyled-link")
                links_on_page = []
                for a in soup.find_all('a', class_='full-unstyled-link'):
                    href = a.get('href', '')
                    if '/products/' in href:
                        if href.startswith('/'):
                            href = self.base_url + href
                        # Nettoyer les paramètres de tracking
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
        with open('beaudegat_product_links.txt', 'w') as f:
            for link in sorted(product_links):
                f.write(link + '\n')
        
        return list(product_links)
    
    def extract_beer_data(self, product_url):
        """Extrait les données structurées d'une bière"""
        try:
            self.driver.get(product_url)
            time.sleep(2)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            beer = {
                'url': product_url,
                'name': None,
                'price': None,
                'producer': None,
                'alcohol': None,
                'volume': None,
                'style': None,
                'description': None,
                'photo_url': None,
                'availability': None
            }
            
            # Nom du produit
            title = soup.find('h1', class_='product__title')
            if title:
                beer['name'] = title.get_text(strip=True)
            
            # Producteur
            producer = soup.find('p', class_='product__text caption-with-letter-spacing')
            if producer:
                beer['producer'] = producer.get_text(strip=True)
            
            # Prix
            price = soup.find('span', class_='price-item price-item--regular')
            if price:
                beer['price'] = price.get_text(strip=True)
            
            # Description complète (div avec classe "product__description rte")
            desc_div = soup.find('div', class_='product__description rte')
            if desc_div:
                # Récupérer tous les paragraphes
                paragraphs = desc_div.find_all('p')
                
                if paragraphs:
                    # Premier paragraphe : contient producteur, alcool, volume
                    first_p = paragraphs[0].get_text(strip=True)
                    
                    # Extraire alcool (ex: "3.4%")
                    alcohol_match = re.search(r'(\d+\.?\d*)\s*%', first_p)
                    if alcohol_match:
                        beer['alcohol'] = alcohol_match.group(1) + '%'
                    
                    # Extraire volume (ex: "473ml")
                    volume_match = re.search(r'(\d+)\s*ml', first_p, re.IGNORECASE)
                    if volume_match:
                        beer['volume'] = volume_match.group(1) + 'ml'
                    
                    # Deuxième paragraphe : contient le style (ex: "HOUBLONNÉE")
                    if len(paragraphs) > 1:
                        second_p = paragraphs[1].get_text(strip=True)
                        # Le style est souvent en majuscules et court
                        # Extraire le texte après l'image (icône) s'il y en a une
                        style_text = second_p.replace('\xa0', ' ').strip()
                        # Garder uniquement le texte en majuscules (style)
                        style_parts = [part.strip() for part in style_text.split() if part.isupper() and len(part) > 2]
                        if style_parts:
                            beer['style'] = ' '.join(style_parts)
                    
                    # Troisième paragraphe et suivants : description complète
                    if len(paragraphs) > 2:
                        description_parts = []
                        for p in paragraphs[2:]:
                            text = p.get_text(strip=True)
                            if text:
                                description_parts.append(text)
                        beer['description'] = ' '.join(description_parts)
            
            # Photo principale (Open Graph image)
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                photo_url = og_image['content'].split('?')[0]
                if photo_url.startswith('//'):
                    photo_url = 'https:' + photo_url
                beer['photo_url'] = photo_url
            
            # Si pas trouvé, chercher dans les images du produit
            if not beer['photo_url']:
                img = soup.find('img', {'srcset': True})
                if img and img.get('src'):
                    src = img['src']
                    if src.startswith('//'):
                        src = 'https:' + src
                    beer['photo_url'] = src.split('?')[0]
            
            # Disponibilité
            sold_out = soup.find('span', class_='badge price__badge-sold-out')
            if sold_out:
                beer['availability'] = 'Épuisé'
            else:
                in_stock = soup.find('pickup-availability')
                if in_stock:
                    beer['availability'] = 'En stock'
                else:
                    beer['availability'] = 'Inconnu'
            
            return beer
            
        except Exception as e:
            print(f"  ✗ Erreur: {e}")
            return None
    
    def save_progress(self, filename='beers_beaudegat.json'):
        """Sauvegarde le progrès actuel en JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.beers, f, ensure_ascii=False, indent=2)
    
    def crawl(self, json_filename='beers_beaudegat.json'):
        """Crawl principal avec sauvegarde progressive"""
        print("🍺 Début du crawling de Beaudegat.ca\n")
        
        try:
            # 1. Récupérer tous les liens
            product_links = self.get_all_product_links()
            
            # 2. Crawler chaque produit
            print("📸 Extraction des données de chaque bière...\n")
            for i, url in enumerate(product_links, 1):
                product_name = url.split('/')[-1]
                print(f"[{i}/{len(product_links)}] {product_name}")
                
                beer = self.extract_beer_data(url)
                
                if beer:
                    self.beers.append(beer)
                    print(f"  ✓ {beer['name']}")
                    print(f"  🏭 {beer['producer']}")
                    print(f"  💰 {beer['price']}")
                    if beer['alcohol']:
                        print(f"  🍺 {beer['alcohol']} - {beer['volume']}")
                    if beer['style']:
                        print(f"  🎨 {beer['style']}")
                    if beer['photo_url']:
                        print(f"  📸 Photo disponible")
                    
                    # Sauvegarder après chaque bière
                    self.save_progress(json_filename)
                    print(f"  💾 Sauvegardé ({len(self.beers)} bières)\n")
                
                time.sleep(1)  # Pause entre les requêtes
            
            print(f"\n🎉 Crawling terminé!")
            print(f"  Total bières: {len(self.beers)}")
            beers_with_photos = sum(1 for b in self.beers if b.get('photo_url'))
            print(f"  Bières avec photo: {beers_with_photos}")
            beers_with_alcohol = sum(1 for b in self.beers if b.get('alcohol'))
            print(f"  Bières avec alcool: {beers_with_alcohol}")
            
        finally:
            self.driver.quit()
        
        return self.beers


# ===== UTILISATION =====
if __name__ == "__main__":
    # headless=True pour mode silencieux, False pour voir le navigateur
    crawler = BeaudegatCrawler(headless=True)
    
    # Lancer le crawling (sauvegarde automatique après chaque bière)
    beers = crawler.crawl('beers_beaudegat.json')
    
    print("\n✅ Terminé! Le fichier beers_beaudegat.json contient toutes les bières.")
    
    if beers:
        print("\n📋 Exemple de bière:")
        print(json.dumps(beers[0], indent=2, ensure_ascii=False))