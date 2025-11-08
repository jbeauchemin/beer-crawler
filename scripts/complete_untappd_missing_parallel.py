#!/usr/bin/env python3
"""
Script PARALLÈLE pour compléter les données Untappd manquantes (description et style)
pour les bières qui ont déjà un untappd_id mais des champs null.

Version optimisée pour M1/M2 MacBook avec multiprocessing.
"""

import json
import time
import multiprocessing as mp
from pathlib import Path
from datetime import datetime
from typing import List, Dict

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


def init_driver():
    """Initialise un driver Selenium (appelé par chaque worker)"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

    if HAS_WEBDRIVER_MANAGER:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)

    return driver


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


def process_chunk(args):
    """
    Traite un chunk de bières (appelé par chaque worker)

    Args:
        args: tuple (beers_chunk, chunk_id)

    Returns:
        dict avec chunk_id, beers enrichies et stats
    """
    beers_chunk, chunk_id = args

    # Initialise le driver pour ce worker
    try:
        driver = init_driver()
        print(f"[Worker {chunk_id}] ✓ Selenium initialisé")
    except Exception as e:
        print(f"[Worker {chunk_id}] ❌ Erreur Selenium: {e}")
        return {
            'chunk_id': chunk_id,
            'beers': beers_chunk,
            'stats': {
                'completed': 0,
                'description_added': 0,
                'style_added': 0,
                'errors': len(beers_chunk)
            }
        }

    stats = {
        'completed': 0,
        'description_added': 0,
        'style_added': 0,
        'errors': 0
    }

    print(f"[Worker {chunk_id}] 🚀 Démarrage - {len(beers_chunk)} bières à traiter")

    for i, beer in enumerate(beers_chunk):
        # Affiche progression tous les 5 items
        if i % 5 == 0 and i > 0:
            print(f"[Worker {chunk_id}] 📊 {i}/{len(beers_chunk)}")

        has_description = beer.get('untappd_description') is not None
        has_style = beer.get('untappd_style') is not None

        # Scrape la page
        scraped = scrape_untappd_page(driver, beer['untappd_url'])

        if scraped:
            added_something = False

            if not has_description and scraped.get('description'):
                stats['description_added'] += 1
                added_something = True

            if not has_style and scraped.get('style'):
                stats['style_added'] += 1
                added_something = True

            if added_something:
                merge_untappd_data(beer, scraped)
                stats['completed'] += 1
        else:
            stats['errors'] += 1

        # Petit délai entre requêtes
        time.sleep(1.5)

    # Ferme le driver
    driver.quit()
    print(f"[Worker {chunk_id}] ✅ Terminé - {stats['completed']} complétées")

    return {
        'chunk_id': chunk_id,
        'beers': beers_chunk,
        'stats': stats
    }


def complete_missing_data_parallel(num_workers: int = 4):
    """
    Complète les données Untappd manquantes en parallèle

    Args:
        num_workers: Nombre de workers parallèles (défaut: 4)
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
    print("🚀 COMPLÉTION PARALLÈLE DES DONNÉES UNTAPPD MANQUANTES")
    print("="*80)
    print(f"Fichier d'entrée:  {input_file}")
    print(f"Fichier de sortie: {output_file}")
    print(f"Workers:           {num_workers}")
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
    to_complete_indices = []  # Pour savoir où les réinsérer

    for idx, beer in enumerate(beers):
        if beer.get('untappd_id') and beer.get('untappd_url'):
            has_description = beer.get('untappd_description') is not None
            has_style = beer.get('untappd_style') is not None

            if not has_description or not has_style:
                to_complete.append(beer)
                to_complete_indices.append(idx)

    print(f"   ✓ {len(to_complete)} bières à compléter")

    if len(to_complete) == 0:
        print("\n✅ Aucune donnée à compléter!")
        return

    # Affiche quelques exemples
    print("\n📋 Exemples de bières à compléter:")
    for i in range(min(5, len(to_complete))):
        beer = to_complete[i]
        desc_status = "✓" if beer.get('untappd_description') else "✗"
        style_status = "✓" if beer.get('untappd_style') else "✗"
        print(f"   {i+1}. {beer.get('name')} - Desc:{desc_status} Style:{style_status}")
    if len(to_complete) > 5:
        print(f"   ... et {len(to_complete) - 5} autres")

    # Divise en chunks
    chunk_size = len(to_complete) // num_workers
    if chunk_size == 0:
        chunk_size = 1
        num_workers = len(to_complete)

    chunks = []
    for i in range(num_workers):
        start = i * chunk_size
        end = start + chunk_size if i < num_workers - 1 else len(to_complete)
        chunk = to_complete[start:end]
        if chunk:  # Seulement si le chunk n'est pas vide
            chunks.append((chunk, i))

    print(f"\n📊 Répartition:")
    for chunk, chunk_id in chunks:
        print(f"   Worker {chunk_id}: {len(chunk)} bières")

    # Calcul temps estimé
    beers_per_worker = len(to_complete) / len(chunks)
    estimated_time = beers_per_worker * 2.5  # 2.5 sec par bière en moyenne
    print(f"\n⏱️  Temps estimé: ~{estimated_time/60:.1f} min par worker")
    print(f"   Temps total estimé: ~{estimated_time/60:.1f} min (parallèle)\n")

    print(f"🚀 Démarrage des {len(chunks)} workers...\n")

    # Lance les workers en parallèle
    start_time = time.time()

    with mp.Pool(processes=len(chunks)) as pool:
        results = pool.map(process_chunk, chunks)

    elapsed = time.time() - start_time

    # Reconstitue les données
    print(f"\n📦 Assemblage des résultats...")

    total_stats = {
        'completed': 0,
        'description_added': 0,
        'style_added': 0,
        'errors': 0
    }

    # Réinsère les bières complétées à leur position d'origine
    enriched_offset = 0
    for result in sorted(results, key=lambda x: x['chunk_id']):
        chunk_beers = result['beers']

        # Réinsère chaque bière
        for beer in chunk_beers:
            original_idx = to_complete_indices[enriched_offset]
            beers[original_idx] = beer
            enriched_offset += 1

        # Agrège les stats
        total_stats['completed'] += result['stats']['completed']
        total_stats['description_added'] += result['stats']['description_added']
        total_stats['style_added'] += result['stats']['style_added']
        total_stats['errors'] += result['stats']['errors']

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
    print(f"Bières complétées:         {total_stats['completed']}")
    print(f"Descriptions ajoutées:     {total_stats['description_added']}")
    print(f"Styles ajoutés:            {total_stats['style_added']}")
    print(f"Erreurs:                   {total_stats['errors']}")
    print(f"\nTemps total:               {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Vitesse:                   {len(to_complete)/elapsed:.2f} bières/sec")
    print(f"Workers:                   {len(chunks)}")

    if len(to_complete) > 0:
        success_rate = (total_stats['completed'] / len(to_complete)) * 100
        print(f"Taux de succès:            {success_rate:.1f}%")

    # Temps économisé vs séquentiel
    sequential_time = len(to_complete) * 2.5
    time_saved = sequential_time - elapsed
    print(f"\nTemps économisé:           {time_saved/60:.1f} min vs séquentiel")

    print("="*80)
    print(f"\n✅ Terminé! Backup disponible: {backup_file}")


def main():
    import sys

    if len(sys.argv) > 1:
        try:
            num_workers = int(sys.argv[1])
        except ValueError:
            print("❌ Nombre de workers invalide!")
            print("\nUsage:")
            print("  python complete_untappd_missing_parallel.py [workers]")
            print("\nExemples:")
            print("  python complete_untappd_missing_parallel.py 4    # 4 workers (défaut)")
            print("  python complete_untappd_missing_parallel.py 8    # 8 workers (M1/M2)")
            sys.exit(1)
    else:
        num_workers = 4

    if num_workers < 1 or num_workers > 16:
        print(f"❌ Nombre de workers invalide: {num_workers}")
        print("   Recommandé: 4-8 workers pour M1/M2")
        sys.exit(1)

    print(f"\n⚡ Mode parallèle: {num_workers} workers")
    print(f"💻 Optimisé pour MacBook M1/M2\n")

    complete_missing_data_parallel(num_workers)


if __name__ == "__main__":
    main()
