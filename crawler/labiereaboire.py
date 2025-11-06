# labab_crawler.py
# -*- coding: utf-8 -*-

from __future__ import annotations
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import time
import json
import re
from typing import Optional, List, Dict, Any


class LaBiereABoireCrawler:
    def __init__(self, headless: bool = True, delay_seconds: float = 0.8):
        self.base_url = "https://labiereaboire.com"
        self.listing_url = f"{self.base_url}/biere"
        self.beers: List[Dict[str, Any]] = []
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
    def _clean(s: Optional[str]) -> str:
        return re.sub(r"\s+", " ", (s or "")).strip()

    @staticmethod
    def _extract_volume(text: str) -> Optional[str]:
        m = re.search(r"(\d{2,4})\s*ml", text, flags=re.I)
        return f"{m.group(1)} ml" if m else None

    @staticmethod
    def _extract_abv(text: str) -> Optional[str]:
        # 5.2% alc/vol ; 7% ; 6,9 %
        m = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%(\s*alc/?vol)?", text, flags=re.I)
        return m.group(1).replace(",", ".") + " %" if m else None

    @staticmethod
    def _extract_style_from_short(short_text: str) -> Optional[str]:
        # "Pale Ale Belge - 5.2% alc/vol" → "Pale Ale Belge"
        parts = [p.strip() for p in short_text.split(" - ") if p.strip()]
        if parts:
            if re.search(r"%\s*alc", parts[0], flags=re.I) or (re.search(r"\d", parts[0]) and parts[0].endswith("%")):
                return None
            return parts[0]
        return None

    @staticmethod
    def _extract_upc_from_list(soup: BeautifulSoup) -> Optional[str]:
        # <li><strong>Modèle :</strong> 377100290908</li>
        for li in soup.select("ul.list-unstyled li"):
            strong = li.find("strong")
            if strong and "modèle" in strong.get_text(strip=True).lower():
                text = li.get_text(" ", strip=True)
                text = re.sub(r"(?i)mod[eè]le\s*:\s*", "", text).strip()
                m = re.search(r"([A-Za-z0-9\-_.]+)", text)
                return m.group(1) if m else text
        ul = soup.select_one("ul.list-unstyled")
        if ul:
            t = ul.get_text(" ", strip=True)
            m = re.search(r"(?i)mod[eè]le\s*:\s*([A-Za-z0-9\-_.]+)", t)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _guess_producer_from_name(name: str) -> Optional[str]:
        # "5e Baron - Diversité - 473ml" → "5e Baron"
        parts = [p.strip() for p in name.split(" - ") if p.strip()]
        return parts[0] if parts else None

    # ---------------------------
    # 1) Collecte des URLs produit (pagination ultra-robuste)
    # ---------------------------
    def get_all_product_links_lbab(self, max_pages: int = 300) -> List[str]:
        """
        Listing OpenCart: /biere?limit=100&page=N
        Détection fiable du nombre de pages:
          - parse "Afficher de X à Y sur TOTAL (N Pages)" -> N prioritaire
          - sinon, prend '>|' (dernière page) et lit page=
          - sinon, max des numéros visibles
        Puis boucle 1..last_page ; et en filet de sécurité, continue
        tant qu'on trouve des produits.
        """
        print("📋 Récupération des produits La Bière à Boire...\n")
        product_links_lbab = set()

        def normalize(u: str) -> str:
            u = (u or "").split("#")[0].split("?")[0].rstrip("/")
            if u.startswith("/"):
                u = self.base_url + u
            return u

        def is_product_url(u: str) -> bool:
            # strict /biere/<slug> (pas la page catégorie ni query-string)
            return bool(re.match(rf"^{re.escape(self.base_url)}/biere/[^/][^?#]*$", u))

        def scrape_listing_page(url: str) -> int:
            self.driver.get(url)
            time.sleep(2.0)
            sp = BeautifulSoup(self.driver.page_source, "html.parser")
            found = 0
            # vignettes + titres
            for a in sp.select(
                ".product-layout .image a[href], "
                ".product-layout h4.product-name a[href]"
            ):
                href = normalize(a.get("href", ""))
                if is_product_url(href) and href not in product_links_lbab:
                    product_links_lbab.add(href)
                    found += 1
            print(f"    → {found} nouveaux produits (Total: {len(product_links_lbab)})")
            return found

        # Charger la page 1
        first_url = f"{self.listing_url}?limit=100"
        print(f"  Page 1: {first_url}")
        self.driver.get(first_url)
        time.sleep(2.0)
        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        # 1) Lire "(N Pages)"
        last_page = None
        amt = soup.select_one(".toolbar-amount span, .toolbar-amount")
        if amt:
            txt = " ".join(amt.get_text(" ", strip=True).split())
            m = re.search(r"\((\d+)\s*Pages?\)", txt, flags=re.I)
            if m:
                last_page = int(m.group(1))

        # 2) Sinon, via le lien '>|'
        if last_page is None:
            last_link = None
            for a in soup.select(".pagination a[href]"):
                if a.get_text(strip=True) in {">|", "»|", "Last", "Fin"}:
                    last_link = a["href"]
                    break
            if last_link:
                m = re.search(r"[?&]page=(\d+)", last_link)
                if m:
                    last_page = int(m.group(1))

        # 3) Sinon, max(numbers)
        if last_page is None:
            nums = []
            for a in soup.select(".pagination a, .pagination span"):
                t = a.get_text(strip=True)
                if t.isdigit():
                    nums.append(int(t))
            last_page = max(nums) if nums else 1

        # Cap & log
        last_page = min(last_page, max_pages)
        print(f"  ➜ Pages détectées: {last_page}")

        # Scraper la page 1 (avec la routine homogène)
        scrape_listing_page(first_url)

        # 4) Boucle 2..last_page
        for page in range(2, last_page + 1):
            page_url = f"{self.listing_url}?limit=100&page={page}"
            print(f"  Page {page}: {page_url}")
            scrape_listing_page(page_url)

        # 5) Filet de sécurité : continuer au-delà tant que ça ajoute
        extra_page = last_page + 1
        consecutive_zeros = 0
        while extra_page <= max_pages and consecutive_zeros < 2:
            page_url = f"{self.listing_url}?limit=100&page={extra_page}"
            print(f"  Page {extra_page} (sécu): {page_url}")
            added = scrape_listing_page(page_url)
            if added == 0:
                consecutive_zeros += 1
            else:
                consecutive_zeros = 0
            extra_page += 1

        # Sauvegarde des liens
        with open("product_links_lbab.txt", "w", encoding="utf-8") as f:
            for link in sorted(product_links_lbab):
                f.write(link + "\n")

        print(f"✓ {len(product_links_lbab)} produits collectés au total!\n")
        return list(product_links_lbab)

    # ---------------------------
    # 2) Extraction d'une fiche
    # ---------------------------
    def extract_beer_data(self, product_url: str) -> Optional[Dict[str, Any]]:
        try:
            self.driver.get(product_url)
            time.sleep(2.0)
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

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
                "photo_url": None,
                "upc": None,
            }

            # ---- Nom
            title = soup.select_one("h1.product-name") or soup.find("h1")
            if title:
                beer["name"] = self._clean(title.get_text())

            # ---- Prix
            price_el = soup.select_one(".price-box .price, .price, .regular-price .price")
            if price_el:
                beer["price"] = self._clean(price_el.get_text())

            # ---- Short description (contient style/ABV + texte)
            short = soup.select_one("p.short-des")
            short_text = self._clean(short.get_text(" ")) if short else ""

            # Style (depuis short)
            style_from_short = self._extract_style_from_short(short_text)
            if style_from_short:
                beer["style"] = style_from_short

            # Volume: depuis le nom ou le short
            vol = self._extract_volume(beer["name"] or "") or self._extract_volume(short_text)
            if vol:
                beer["volume"] = vol

            # ABV
            abv = self._extract_abv(short_text)
            if abv:
                beer["alcohol"] = abv

            # Description = short-des (en retirant l’entête "STYLE - ABV" s’il est en tête)
            desc = short_text
            if style_from_short:
                desc = re.sub(
                    r"^" + re.escape(style_from_short) + r"\s*-\s*[\d.,]+\s*%\s*(?:alc/?vol)?\s*",
                    "",
                    desc,
                    flags=re.I,
                )
            beer["description"] = desc if desc else (beer["name"] or None)

            # ---- UPC (depuis Modèle :)
            beer["upc"] = self._extract_upc_from_list(soup)

            # ---- Producer: déduit du name avant premier " - "
            if beer["name"]:
                producer = self._guess_producer_from_name(beer["name"])
                if producer:
                    beer["producer"] = producer

            # ---- Photo principale: préférer le lien haute résolution
            img_a = soup.select_one("ul.thumbnails li a.thumbnail[href]")
            if img_a and img_a.get("href"):
                beer["photo_url"] = img_a["href"].split("?")[0]
            else:
                img = soup.select_one("ul.thumbnails img, .product-image-main img")
                if img and img.get("src"):
                    src = img["src"].split("?")[0]
                    beer["photo_url"] = src if src.startswith("http") else self.base_url + src

            return beer

        except Exception as e:
            print(f"  ✗ Erreur sur {product_url}: {e}")
            return None

    # ---------------------------
    # 3) Sauvegarde
    # ---------------------------
    def save_progress(self, filename: str = "beers_lbab.json") -> None:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.beers, f, ensure_ascii=False, indent=2)

    # ---------------------------
    # 4) Crawl principal
    # ---------------------------
    def crawl(self, json_filename: str = "beers_lbab.json") -> List[Dict[str, Any]]:
        print("🍺 Début du crawling La Bière à Boire\n")
        try:
            product_links_lbab = self.get_all_product_links_lbab()
            print("📸 Extraction des données...\n")

            for i, url in enumerate(product_links_lbab, 1):
                slug = url.rstrip("/").split("/")[-1]
                print(f"[{i}/{len(product_links_lbab)}] {slug}")

                beer = self.extract_beer_data(url)
                if beer:
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
    crawler = LaBiereABoireCrawler(headless=True, delay_seconds=0.8)
    beers = crawler.crawl("beers_lbab.json")
    print("\n✅ Terminé! Le fichier beers_lbab.json contient toutes les bières.")
    if beers:
        print("\n📋 Exemple de bière:")
        print(json.dumps(beers[0], indent=2, ensure_ascii=False))