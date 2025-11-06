# espace_houblon.py
# -*- coding: utf-8 -*-

from __future__ import annotations
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import itertools
import time
import json
import re
from typing import Optional, List, Dict, Any


class EspaceHoublonCrawler:
    def __init__(self, headless: bool = True, only_beer: bool = True, delay_seconds: float = 1.0):
        """
        :param headless: lance Chrome en mode headless
        :param only_beer: si True, ne conserve que les produits catégorisés "Bière"
        :param delay_seconds: délai entre les requêtes produit (respect du site)
        """
        self.base_url = "https://espacehoublon.ca"
        self.listing_url = f"{self.base_url}/produits/"
        self.beers: List[Dict[str, Any]] = []
        self.only_beer = only_beer
        self.delay_seconds = max(0.3, delay_seconds)

        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 12)

    # ---------------------------
    # Utils
    # ---------------------------
    @staticmethod
    def _clean_text(s: Optional[str]) -> str:
        return re.sub(r"\s+", " ", (s or "")).strip()

    @staticmethod
    def _parse_info_line(line: str) -> Dict[str, Optional[str]]:
        """
        Parse une ligne du type "Smoothie | 473 ml | 5,2%" en {style, volume, alcohol}
        """
        result = {"style": None, "volume": None, "alcohol": None}
        tokens = [t.strip(" .") for t in re.split(r"\s*\|\s*", line) if t.strip()]
        # Style = 1er token non numérique
        if tokens and not re.search(r"\d", tokens[0]):
            result["style"] = tokens[0]
        # Volume
        for t in tokens:
            m = re.search(r"(\d{2,4})\s*ml", t, flags=re.I)
            if m:
                result["volume"] = f"{m.group(1)} ml"
                break
        # Alcool
        for t in tokens:
            m = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%", t)
            if m:
                result["alcohol"] = m.group(1).replace(",", ".") + " %"
                break
        return result

    def _should_keep_as_beer(self, soup: BeautifulSoup) -> bool:
        """
        Retourne True si le produit est catégorisé "Bière" (utile pour filtrer verres/cadeaux/etc.)
        """
        if not self.only_beer:
            return True
        for a in soup.select(".product-meta .product-category a, .product_meta .posted_in a"):
            label = self._clean_text(a.get_text())
            if label.lower() in {"bière", "biere"}:
                return True
        return False

    # ---------------------------
    # 1) Collecte des URLs produit
    # ---------------------------
    def get_all_product_links_espace_houblon(self, max_pages: int = 300) -> List[str]:
        """
        Espace Houblon: listing en /produits/ puis /produits/page/{n}/
        On collecte les <a> vers /produit/{slug}
        """
        print("📋 Récupération de tous les produits Espace Houblon...\n")
        product_links_espace_houblon = set()

        for page in range(1, max_pages + 1):
            url = self.listing_url if page == 1 else f"{self.listing_url}page/{page}/"
            print(f"  Page {page}: {url}")
            try:
                self.driver.get(url)
                time.sleep(2.0)

                html = self.driver.page_source
                soup = BeautifulSoup(html, "html.parser")

                found = 0
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if re.search(r"/produit/[^/]+/?$", href):
                        if href.startswith("/"):
                            href = self.base_url + href
                        href = href.split("?")[0].rstrip("/")
                        if href not in product_links_espace_houblon:
                            product_links_espace_houblon.add(href)
                            found += 1

                if found == 0:
                    print("  ✓ Aucun nouveau produit sur cette page → arrêt.\n")
                    break

                print(f"    → {found} nouveaux produits (Total: {len(product_links_espace_houblon)})\n")

            except Exception as e:
                print(f"  ✗ Erreur page {page}: {e}")
                break

        with open("product_links_espace_houblon.txt", "w", encoding="utf-8") as f:
            for link in sorted(product_links_espace_houblon):
                f.write(link + "\n")

        print(f"✓ {len(product_links_espace_houblon)} produits collectés au total!\n")
        return list(product_links_espace_houblon)

    # ---------------------------
    # 2) Extraction d'une fiche
    # ---------------------------
    def extract_beer_data(self, product_url: str) -> Optional[Dict[str, Any]]:
        """
        Extrait: name, price, producer, style, sub_style, volume, alcohol, description, photo_url
        Cible un thème WooCommerce (structure confirmée).
        """
        try:
            # micro retry pour sûreté
            for attempt in range(2):
                self.driver.get(product_url)
                time.sleep(2.0)
                html = self.driver.page_source
                if "class=\"product-details-wrapper\"" in html or "class=\"product-name\"" in html:
                    break
                time.sleep(1.0)

            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Filtre optionnel “Bière”
            if not self._should_keep_as_beer(soup):
                print("  ↪️ Ignoré (pas dans la catégorie Bière)")
                return None

            beer: Dict[str, Any] = {
                "url": product_url,
                "name": None,
                "price": None,
                "producer": None,
                "style": None,
                "sub_style": None,
                "volume": None,
                "alcohol": None,
                "description": None,
                "photo_url": None
            }

            # ---- Nom
            title = soup.select_one("h1.product-name, h1.product_title, h1.product-name.product_title, h1")
            if title:
                beer["name"] = self._clean_text(title.get_text())

            # ---- Prix (WooCommerce)
            price_el = soup.select_one(".product-price .woocommerce-Price-amount") \
                       or soup.select_one(".summary .price .woocommerce-Price-amount") \
                       or soup.select_one(".summary .price")
            if price_el:
                beer["price"] = self._clean_text(price_el.get_text())

            # ---- Wrapper produit
            wrapper = soup.select_one(".product-details-wrapper") or soup.select_one(".summary") or soup

            # ---- Premier <p> direct sous wrapper → "Smoothie | 473 ml | 5,2%"
            p_info = None
            try:
                p_info = wrapper.select_one(":scope > p")  # enfants directs
            except Exception:
                # fallback soupsieve
                for child in wrapper.children:
                    if getattr(child, "name", None) == "p":
                        p_info = child
                        break
                if not p_info:
                    p_info = wrapper.find("p")

            if p_info:
                info_line = self._clean_text(p_info.get_text(" "))
                parsed = self._parse_info_line(info_line)
                # Style depuis la ligne info
                if parsed["style"]:
                    beer["style"] = parsed["style"]
                if parsed["volume"]:
                    beer["volume"] = parsed["volume"]
                if parsed["alcohol"]:
                    beer["alcohol"] = parsed["alcohol"]

            # ---- Description: concat des div[dir="auto"] qui suivent p_info
            desc_parts: List[str] = []
            if p_info is not None:
                for sib in p_info.next_siblings:
                    # uniquement les blocs <div dir="auto"> qui suivent immédiatement
                    if getattr(sib, "name", None) != "div" or sib.get("dir") != "auto":
                        # si on tombe sur un autre gros bloc, on arrête (on reste dans la zone description)
                        if getattr(sib, "name", None) in {"div", "section", "form", "ul", "ol"}:
                            break
                        continue
                    txt = self._clean_text(sib.get_text(" "))
                    if not txt:
                        continue
                    # filtrer le GDPR / bannières
                    if "Le stockage ou l’accès technique" in txt or "communications électroniques" in txt:
                        continue
                    desc_parts.append(txt)

            if not desc_parts:
                # fallback doux: tout div[dir='auto'] sous wrapper
                for d in wrapper.select("div[dir='auto']"):
                    txt = self._clean_text(d.get_text(" "))
                    if txt and "Le stockage ou l’accès technique" not in txt:
                        desc_parts.append(txt)

            if desc_parts:
                beer["description"] = " ".join(desc_parts)

            # ---- Catégories → producer / (sub_)style
            for a in soup.select(".product-meta .product-category a, .product_meta .posted_in a"):
                href = a.get("href", "")
                label = self._clean_text(a.get_text())
                if not label:
                    continue
                # Producer
                if "/categorie-produit/biere/microbrasserie/" in href:
                    if not beer["producer"]:
                        beer["producer"] = label
                # Style (fallback ou sub_style)
                elif "/categorie-produit/biere/style/" in href:
                    if beer["style"] and label.lower() != (beer["style"] or "").lower():
                        if not beer["sub_style"]:
                            beer["sub_style"] = label
                    elif not beer["style"]:
                        beer["style"] = label
                else:
                    # autre catégorie (ex. Bière) -> ignorée ici
                    pass

            # ---- Image principale
            og = soup.find("meta", property="og:image")
            if og and og.get("content"):
                img = og["content"].split("?")[0]
                beer["photo_url"] = img if img.startswith("http") else ("https:" + img)

            if not beer["photo_url"]:
                gal_img = soup.select_one(
                    ".product-slider-main img, "
                    ".woocommerce-product-gallery__image img, "
                    ".woocommerce-product-gallery img"
                )
                if gal_img:
                    src = gal_img.get("data-large_image") or gal_img.get("data-src") or gal_img.get("src")
                    if src:
                        src = src.split("?")[0]
                        if src.startswith("http"):
                            beer["photo_url"] = src
                        elif src.startswith("/"):
                            beer["photo_url"] = self.base_url + src
                        else:
                            beer["photo_url"] = "https:" + src

            # ---- Normalisation éventuelle style -> sub_style si séparateurs
            if beer["style"] and not beer["sub_style"]:
                parts = re.split(r"[–—\-\/>|]+", beer["style"])
                if len(parts) > 1:
                    beer["style"] = parts[0].strip()
                    beer["sub_style"] = parts[1].strip()

            return beer

        except Exception as e:
            print(f"  ✗ Erreur sur {product_url}: {e}")
            return None

    # ---------------------------
    # 3) Sauvegardes
    # ---------------------------
    def save_progress(self, filename: str = "beers_espacehoublon.json") -> None:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.beers, f, ensure_ascii=False, indent=2)

    # ---------------------------
    # 4) Crawl principal
    # ---------------------------
    def crawl(self, json_filename: str = "beers_espacehoublon.json") -> List[Dict[str, Any]]:
        print("🍺 Début du crawling Espace Houblon\n")
        try:
            product_links_espace_houblon = self.get_all_product_links_espace_houblon()
            print("📸 Extraction des données...\n")

            for i, url in enumerate(product_links_espace_houblon, 1):
                slug = url.rstrip("/").split("/")[-1]
                print(f"[{i}/{len(product_links_espace_houblon)}] {slug}")

                beer = self.extract_beer_data(url)
                if beer:
                    # si only_beer=True et que _should_keep_as_beer a refusé, beer=None
                    self.beers.append(beer)
                    print(f"  ✓ {beer.get('name')}")
                    if beer.get("photo_url"):
                        print(f"  📸 {beer['photo_url']}")
                    self.save_progress(json_filename)
                    print(f"  💾 Sauvegardé ({len(self.beers)} bières)\n")

                time.sleep(self.delay_seconds)

            print("\n🎉 Crawling terminé!")
            print(f"  Total bières: {len(self.beers)}")
            beers_with_photos = sum(1 for b in self.beers if b.get("photo_url"))
            print(f"  Bières avec photo: {beers_with_photos}")

        finally:
            self.driver.quit()

        return self.beers


# ===== UTILISATION =====
if __name__ == "__main__":
    # headless=True, only_beer=True (par défaut) : exclut les produits non "Bière"
    crawler = EspaceHoublonCrawler(headless=True, only_beer=True, delay_seconds=1.0)
    beers = crawler.crawl("beers_espacehoublon.json")

    print("\n✅ Terminé! Le fichier beers_espacehoublon.json contient toutes les bières.")
    if beers:
        print("\n📋 Exemple de bière:")
        print(json.dumps(beers[0], indent=2, ensure_ascii=False))