#!/usr/bin/env python3
"""
Script pour compléter les données Untappd manquantes (description et style)
pour les bières qui ont déjà un untappd_id mais des champs null.

Ce script utilise Selenium pour scraper les pages Untappd.
Il fonctionne en mode SÉQUENTIEL (pas parallèle) car Selenium ne supporte pas bien le multiprocessing.
"""

import json
import time
from pathlib import Path
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from bs4 import BeautifulSoup
    HAS_SELENIUM = True

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        HAS_WEBDRIVER_MANAGER = True
    except ImportError:
        HAS_WEBDRIVER_MANAGER = False

except ImportError:
    HAS_SELENIUM = False
    HAS_WEBDRIVER_MANAGER = False
    print("❌ Selenium et BeautifulSoup4 requis pour ce script!")
    print("   Installez avec: pip install -r requirements_scraping.txt")
    exit(1)


def scrape_untappd_page(driver, url: str) -> dict:
    """
    Scrape une page Untappd pour extraire description et style

    Args:
        driver: Instance Selenium WebDriver
        url: URL de la bière sur Untappd

    Returns:
        dict avec 'description' et 'style', ou {} si erreur
    """
    try:
        driver.get(url)
        time.sleep(2)  # Attendre le chargement de la page

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        result = {}

        # Description
        desc_div = soup.find('div', class_='beer-descrption-read-less')
        if desc_div:
            result['description'] = desc_div.get_text(strip=True)

        # Style
        style_elem = soup.find('p', class_='style')
        if style_elem:
            result['style'] = style_elem.get_text(strip=True)

        return result

    except Exception as e:
        print(f"      ⚠️  Erreur scraping {url}: {e}")
        return {}


def normalize_url(url: str) -> str:
    """Convertit http:// en https://"""
    if url and url.startswith('http://'):
        return url.replace('http://', 'https://', 1)
    return url


def merge_untappd_data(beer: dict, scraped_data: dict):
    """
    Fusionne les données scrapées dans la structure de la bière

    Args:
        beer: Dictionnaire de la bière à modifier
        scraped_data: Données scrapées (description, style)
    """
    # Ajoute dans les champs untappd_*
    if scraped_data.get('description'):
        beer['untappd_description'] = scraped_data['description']

    if scraped_data.get('style'):
        beer['untappd_style'] = scraped_data['style']

    # Fusionne dans descriptions{}
    if 'descriptions' not in beer:
        beer['descriptions'] = {}
    if scraped_data.get('description'):
        beer['descriptions']['untappd'] = scraped_data['description']

    # Fusionne dans styles{}
    if 'styles' not in beer:
        beer['styles'] = {}
    if scraped_data.get('style'):
        beer['styles']['untappd'] = scraped_data['style']

    # Normalise les URLs
    if beer.get('untappd_url'):
        beer['untappd_url'] = normalize_url(beer['untappd_url'])
    if beer.get('untappd_label'):
        beer['untappd_label'] = normalize_url(beer['untappd_label'])


def complete_missing_data():
    """
    Complète les données Untappd manquantes pour toutes les bières
    qui ont un untappd_id mais description ou style null
    """

    # Chemins des fichiers
    input_file = Path('../data/beers_merged.json')
    if not input_file.exists():
        input_file = Path('../datas/beers_merged.json')

    if not input_file.exists():
        print("❌ Erreur: Fichier beers_merged.json introuvable!")
        return

    output_file = input_file
    backup_file = input_file.parent / f"{input_file.stem}_complete_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    print("="*80)
    print("🔄 COMPLÉTION DES DONNÉES UNTAPPD MANQUANTES")
    print("="*80)
    print(f"Fichier d'entrée:  {input_file}")
    print(f"Fichier de sortie: {output_file}")
    print("="*80)

    # Charge les données
    print("\n📂 Chargement des données...")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            beers = json.load(f)
        print(f"   ✓ {len(beers)} bières chargées")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return

    # Crée le backup
    print(f"\n💾 Création du backup...")
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(beers, f, ensure_ascii=False, indent=2)
        print(f"   ✓ Backup: {backup_file}")
    except Exception as e:
        print(f"   ⚠️  Backup impossible: {e}")

    # Filtre les bières à compléter
    print("\n🔍 Recherche des bières à compléter...")
    to_complete = []
    for beer in beers:
        if beer.get('untappd_id') and beer.get('untappd_url'):
            has_description = beer.get('untappd_description') is not None
            has_style = beer.get('untappd_style') is not None

            if not has_description or not has_style:
                to_complete.append(beer)

    print(f"   ✓ {len(to_complete)} bières à compléter")

    if len(to_complete) == 0:
        print("\n✅ Aucune donnée à compléter!")
        return

    # Affiche quelques exemples
    print("\n📋 Exemples de bières à compléter:")
    for i, beer in enumerate(to_complete[:5]):
        desc_status = "✓" if beer.get('untappd_description') else "✗"
        style_status = "✓" if beer.get('untappd_style') else "✗"
        print(f"   {i+1}. {beer.get('name')} - Desc:{desc_status} Style:{style_status}")
    if len(to_complete) > 5:
        print(f"   ... et {len(to_complete) - 5} autres")

    # Initialise Selenium
    print("\n🌐 Initialisation de Selenium...")
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        if HAS_WEBDRIVER_MANAGER:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("   ✓ Selenium avec webdriver-manager")
        else:
            driver = webdriver.Chrome(options=chrome_options)
            print("   ✓ Selenium avec ChromeDriver système")

    except Exception as e:
        print(f"   ❌ Impossible d'initialiser Selenium: {e}")
        print("\n   SOLUTIONS:")
        print("   1. Installez: pip install -r requirements_scraping.txt")
        print("   2. Ou lancez: python test_selenium_setup.py pour diagnostiquer")
        return

    # Statistiques
    stats = {
        'completed': 0,
        'description_added': 0,
        'style_added': 0,
        'errors': 0
    }

    # Traite chaque bière
    print(f"\n🚀 Début du scraping ({len(to_complete)} bières)...")
    print("   (Cela peut prendre plusieurs minutes, soyez patient)\n")

    start_time = time.time()

    for i, beer in enumerate(to_complete):
        print(f"{i+1}/{len(to_complete)}. 🔄 {beer.get('name')}")
        print(f"   URL: {beer.get('untappd_url')}")

        has_description = beer.get('untappd_description') is not None
        has_style = beer.get('untappd_style') is not None

        # Scrape la page
        scraped = scrape_untappd_page(driver, beer['untappd_url'])

        if scraped:
            added_something = False

            if not has_description and scraped.get('description'):
                print(f"   📄 Description: {scraped['description'][:80]}...")
                stats['description_added'] += 1
                added_something = True

            if not has_style and scraped.get('style'):
                print(f"   🎨 Style: {scraped['style']}")
                stats['style_added'] += 1
                added_something = True

            if added_something:
                merge_untappd_data(beer, scraped)
                stats['completed'] += 1
            else:
                print(f"   ⚠️  Aucune donnée trouvée sur la page")
                stats['errors'] += 1
        else:
            print(f"   ❌ Erreur scraping")
            stats['errors'] += 1

        # Affiche progression tous les 10 items
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = (len(to_complete) - (i + 1)) / rate if rate > 0 else 0
            print(f"\n   📊 Progression: {i+1}/{len(to_complete)} ({(i+1)*100//len(to_complete)}%)")
            print(f"   ⏱️  Temps écoulé: {elapsed:.0f}s | Restant: ~{remaining:.0f}s\n")

        # Délai entre requêtes
        time.sleep(2)

    # Ferme le driver
    driver.quit()

    elapsed = time.time() - start_time

    # Sauvegarde
    print(f"\n💾 Sauvegarde des résultats...")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(beers, f, ensure_ascii=False, indent=2)
        print(f"   ✓ Sauvegardé: {output_file}")
    except Exception as e:
        print(f"   ❌ Erreur sauvegarde: {e}")
        return

    # Statistiques finales
    print("\n" + "="*80)
    print("📊 STATISTIQUES FINALES")
    print("="*80)
    print(f"Bières à compléter:        {len(to_complete)}")
    print(f"Bières complétées:         {stats['completed']}")
    print(f"Descriptions ajoutées:     {stats['description_added']}")
    print(f"Styles ajoutés:            {stats['style_added']}")
    print(f"Erreurs:                   {stats['errors']}")
    print(f"\nTemps total:               {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Vitesse:                   {len(to_complete)/elapsed:.2f} bières/sec")

    if len(to_complete) > 0:
        success_rate = (stats['completed'] / len(to_complete)) * 100
        print(f"Taux de succès:            {success_rate:.1f}%")

    print("="*80)
    print(f"\n✅ Terminé! Backup disponible: {backup_file}")


if __name__ == "__main__":
    complete_missing_data()
