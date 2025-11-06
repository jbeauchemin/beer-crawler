from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import json
import re

class VTUBCrawler:
    def __init__(self, headless=True):
        self.base_url = "https://veuxtuunebiere.com"
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
    
    def get_all_product_links(self, collection_path):
        """Récupère tous les liens en parcourant toutes les pages d'une collection"""
        collection_name = collection_path.split('/')[-1]
        print(f"📋 Récupération des produits de '{collection_name}'...\n")
        
        product_links = set()
        page = 1
        max_pages = 100  # Limite de sécurité
        
        while page <= max_pages:
            url = f"{self.base_url}/{collection_path}?page={page}"
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
                    if '/products/' in href:
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
        
        print(f"✓ {len(product_links)} produits dans '{collection_name}'!\n")
        
        return list(product_links)
    
    def extract_beer_data(self, product_url, is_alcohol_free=False):
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
                'description': None,
                'photo_url': None
            }
            
            # Nom
            title = soup.find('h1')
            if title:
                beer['name'] = title.get_text(strip=True)
            
            # Prix
            price_selectors = [
                soup.find(class_=re.compile(r'price', re.I)),
                soup.find('span', {'data-product-price': True}),
                soup.find(attrs={'data-price': True})
            ]
            for price in price_selectors:
                if price:
                    beer['price'] = price.get_text(strip=True)
                    break
            
            # Informations structurées
            alcohol_found = False
            for element in soup.find_all(['li', 'div', 'p', 'span']):
                text = element.get_text(strip=True)
                
                if 'Producteur' in text:
                    link = element.find('a')
                    if link:
                        beer['producer'] = link.get_text(strip=True)
                    else:
                        match = re.search(r'Producteur\s*:?\s*(.+?)(?:\n|$)', text)
                        if match:
                            beer['producer'] = match.group(1).strip()
                
                if 'Style' in text and 'Sous' not in text:
                    link = element.find('a')
                    if link:
                        beer['style'] = link.get_text(strip=True)
                    else:
                        match = re.search(r'Style\s*:?\s*(.+?)(?:\n|$)', text)
                        if match:
                            beer['style'] = match.group(1).strip()
                
                if 'Sous-Style' in text or 'Sous-style' in text:
                    link = element.find('a')
                    if link:
                        beer['sub_style'] = link.get_text(strip=True)
                    else:
                        match = re.search(r'Sous-[Ss]tyle\s*:?\s*(.+?)(?:\n|$)', text)
                        if match:
                            beer['sub_style'] = match.group(1).strip()
                
                if 'Volume' in text:
                    match = re.search(r'(\d+\s*ml)', text)
                    if match:
                        beer['volume'] = match.group(1)
                
                if 'Alcool' in text:
                    match = re.search(r'(\d+\.?\d*\s*%)', text)
                    if match:
                        beer['alcohol'] = match.group(1)
                        alcohol_found = True
            
            # Si c'est une bière sans alcool et qu'aucun % n'a été trouvé
            if is_alcohol_free and not alcohol_found:
                beer['alcohol'] = "0.0%"
            
            # Description
            desc_selectors = [
                soup.find(class_=re.compile(r'description', re.I)),
                soup.find(class_=re.compile(r'product.*desc', re.I)),
                soup.find('div', attrs={'itemprop': 'description'})
            ]
            for desc in desc_selectors:
                if desc:
                    beer['description'] = desc.get_text(strip=True)
                    break
            
            # Photo principale (Open Graph image)
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                photo_url = og_image['content'].split('?')[0]
                if photo_url.startswith('//'):
                    photo_url = 'https:' + photo_url
                beer['photo_url'] = photo_url
            
            # Si pas trouvé, chercher l'image principale
            if not beer['photo_url']:
                main_img = soup.find('img', class_=re.compile(r'product.*image|main.*image', re.I))
                if main_img:
                    src = main_img.get('src') or main_img.get('data-src')
                    if src:
                        photo_url = src.split('?')[0]
                        if photo_url.startswith('//'):
                            photo_url = 'https:' + photo_url
                        beer['photo_url'] = photo_url
            
            return beer
            
        except Exception as e:
            print(f"  ✗ Erreur: {e}")
            return None
    
    def save_progress(self, filename='beers_vtub.json'):
        """Sauvegarde le progrès actuel en JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.beers, f, ensure_ascii=False, indent=2)
    
    def crawl_collection(self, collection_path, is_alcohol_free=False):
        """Crawl une collection spécifique"""
        product_links = self.get_all_product_links(collection_path)
        
        print(f"📸 Extraction des données de chaque bière...\n")
        for i, url in enumerate(product_links, 1):
            product_name = url.split('/')[-1]
            print(f"[{i}/{len(product_links)}] {product_name}")
            
            beer = self.extract_beer_data(url, is_alcohol_free)
            
            if beer:
                self.beers.append(beer)
                print(f"  ✓ {beer['name']}")
                if beer['alcohol']:
                    print(f"  🍺 Alcool: {beer['alcohol']}")
                if beer['photo_url']:
                    print(f"  📸 {beer['photo_url']}")
                
                # Sauvegarder après chaque bière
                self.save_progress()
                print(f"  💾 Sauvegardé ({len(self.beers)} bières)\n")
            
            time.sleep(1)
    
    def crawl(self, json_filename='beers_vtub.json'):
        """Crawl principal avec sauvegarde progressive"""
        print("🍺 Début du crawling de Veux-tu une bière\n")
        print("=" * 60 + "\n")
        
        try:
            # 1. Crawler les bières alcoolisées
            print("🍺 SECTION 1: Bières alcoolisées\n")
            self.crawl_collection('collections/toutes-les-bieres', is_alcohol_free=False)
            
            print("\n" + "=" * 60 + "\n")
            
            # 2. Crawler les bières sans alcool
            print("🥤 SECTION 2: Bières sans alcool\n")
            self.crawl_collection('collections/bieres-sans-alcool', is_alcohol_free=True)
            
            print("\n" + "=" * 60 + "\n")
            print(f"🎉 Crawling terminé!")
            print(f"  Total bières: {len(self.beers)}")
            
            beers_with_photos = sum(1 for b in self.beers if b.get('photo_url'))
            print(f"  Bières avec photo: {beers_with_photos}")
            
            alcohol_free = sum(1 for b in self.beers if b.get('alcohol') == "0.0%")
            print(f"  Bières sans alcool: {alcohol_free}")
            
        finally:
            self.driver.quit()
        
        return self.beers
    
    def save_to_json(self, filename='beers_vtub.json'):
        """Sauvegarde finale en JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.beers, f, ensure_ascii=False, indent=2)
        print(f"💾 Sauvegarde finale dans {filename}")


# ===== UTILISATION =====
if __name__ == "__main__":
    # headless=True pour mode silencieux, False pour voir le navigateur
    crawler = VTUBCrawler(headless=True)
    
    # Lancer le crawling (sauvegarde automatique après chaque bière)
    beers = crawler.crawl('beers_vtub.json')
    
    print("\n✅ Terminé! Le fichier beers_vtub.json contient toutes les bières.")
    
    # python main.py  
    if beers:
        print("\n📋 Exemples de bières:")
        
        # Exemple de bière alcoolisée
        alcoholic = next((b for b in beers if b.get('alcohol') and b['alcohol'] != "0.0%"), None)
        if alcoholic:
            print("\n🍺 Bière alcoolisée:")
            print(json.dumps(alcoholic, indent=2, ensure_ascii=False))
        
        # Exemple de bière sans alcool
        non_alcoholic = next((b for b in beers if b.get('alcohol') == "0.0%"), None)
        if non_alcoholic:
            print("\n🥤 Bière sans alcool:")
            print(json.dumps(non_alcoholic, indent=2, ensure_ascii=False))